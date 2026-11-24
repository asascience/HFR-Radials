# geodesic distance
from geopy.distance import Distance
import requests
import datetime
import geopy
import itertools
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
import xarray as xr
import re
import s3fs
import os
import sys
from io import StringIO
from typing import Union

import json
import logging

logger = logging.getLogger()
logger.setLevel("INFO")

def lambda_handler(event, context):
    # Print the event for debugging purposes
    logger.info("Received event: " + json.dumps(event, indent=2))
    file_errors = []

    # Extract bucket name and object key from the event
    for record in event["Records"]:
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']

        # Construct the S3 file location
        s3_file_location = f"s3://{bucket_name}/{object_key}"

        # Log the S3 file location
        logger.info(f"S3 file location: {s3_file_location}")

        try:
            process_over_file(s3_file_location, ".csv", ",")
        except:
            file_errors.append(s3_file_location)
            logging.exception(f"Exception occurred while processing {s3_file_location}: ")

        if not file_errors:
            return {
                'statusCode': 200,
                'body': json.dumps('File processed successfully!')
            }
        else:
            return {'statusCode': 500,
                    'body': json.dumps(f"The following files failed to process: {file_errors}")}





default_config = {
  "processed_root": "/data/CLEAN",
  "process_metadata": False,
  "metadata_to_vars": []
}

def get_config(config_filepath):
    '''
    get_config(config_filepath)

    This function reads and returns configuration variables
    ---------------------------------------------------------------------- Input:
    config_filepath {str} - an absolute or relative path to the config file

    Output:
    config {obj} - configuation object
    '''

    # NOTE
    # This really should not be part of the "library" functionality,
    # since it's quite specific to the OTT use-case. Remove when
    # ready to create production lib.
    config = {}
    config_file = Path(config_filepath)

    if config_file.is_file():
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        raise Exception('missing config file!')

    return config

def preprocess_metadata(metadata):
    """
    Some values require further processing, such as origin latitude
    and origin longitude. Update the metadata dict in place.

    Args:
        metadata (dict)

    Returns:
        None
    """

    # origin latitude, longitude
    olat, olon = get_olat_olon(metadata)
    metadata['origin_lat'] = olat
    metadata['origin_lon'] = olon
def clean_radial_ascii(buf: StringIO, metadata, metadata_to_vars=[]):
    """
    Args:
        inpath (path-like): path to existing radar ASCII data
        metadata (dictionary): list of metadata information from the radar ASCII data file header
        metadata_to_vars (list-like): list of metadata fields to transform into variables

    Returns:
        pandas.DataFrame
    """

    # get column names from metadata
    col_names = [col_name.decode("utf-8") for col_name in
                 metadata[b"TableColumnTypes"].split(b" ")]

    # read file in as dataframe
    df = pd.read_csv(
        buf,
        header=None,
        sep=r'\s+',
        comment='%', # don't read in lines that are commented
        encoding='utf-8',
        names=col_names
    )

    # assign metadata values as variables
    # TODO -- map func? itertools? functools?
    for m in metadata_to_vars:
        df[m] = metadata.get(m, None) # np.nan?

    # make column names uppercase
    df.columns = list(map(lambda x: x.upper(), df.columns))

    return df

def _rb2ll(lon0, lat0, r, b):
    """Vincenty Distance function.
    :param float lon0, lat0, r(ange), b(earing)
    :return tuple (lon (float), lat (float))"""
    origin = geopy.Point(lat0, lon0) # define the origin using geopy
    d = Distance(kilometers=r).destination(origin, b) # using vincenty distance to get lat/lon from range and bearing
    return d.longitude, d.latitude


def process_over_file(path: str, use_extension=None, use_sep=" ",
                     remove_year_month_path=False):
    cfg = default_config
    # allow loading in of custom destination directory
    if os.environ.get("PROCESSED_ROOT"):
        cfg["processed_root"] = os.environ["PROCESSED_ROOT"]
    fh = None
    try:
        if path.startswith("s3://"):
            s3 = s3fs.S3FileSystem()
            fh = s3.open(path)
        else:
            fh = open(path, "rb")

        metadata = get_metadata_from_file(fh)
        # TODO: refactor to metadata processing method
        # extract the origin latitude and longitude from the metadata
        preprocess_metadata(metadata)
       
        cleaned_fpath, dataset_id  = filepath_from_metadata(path, cfg["processed_root"], metadata, use_extension)
        if remove_year_month_path:
            cleaned_fpath = re.sub(r"\d{4}-\d{2}/", "", cleaned_fpath)

        # if those directories don't exist, make them
        #create_local_dirs(cleaned_fpath)

        # ASCII cleaning config
        #metadata_to_vars = cfg['metadata_to_vars']
        metadata_to_vars = []

        # process and write the file write the file
        df = clean_radial_ascii(path, metadata, metadata_to_vars=metadata_to_vars)

        if len(df) != 0:
            df.to_csv(
               cleaned_fpath,
               sep=use_sep,
               index=False # do not write index
            )
            #logger.info(f"Successfully processed {msg}")
            if os.environ.get("UPDATE_ERDDAP_SERVICE"):
                service_endpoint = os.environ["UPDATE_ERDDAP_SERVICE"]
            else:
                service_endpoint ="http://3.219.116.209:8091/update_erddap/" 
            requests.get(service_endpoint, {"dataset" :f"{dataset_id}"},headers={'api-key':os.environ["FLAG_API_KEY"]})
        else:
            print(f"File {path} does not contain data. Ignoring file") 
    finally:
        if fh is not None:
            fh.close()

def filepath_from_metadata(fpath: Union[str, Path], processed_root, metadata, use_extension: str=None):

    # create path to write cleaned file to
    # if i_ or m_ not in file name, add n_
    file_base = os.path.basename(fpath)
    if 'RDL' not in file_base:
       fpath = fpath.replace(file_base, f"RDL_{file_base}")
    m = re.search(r".*RDL(?![miz]_).*", fpath)
    if m:
        _fpath = re.sub("RDL_", "RDLn_", fpath, 1)
    else:
        _fpath = fpath
        
    site = os.path.basename(fpath).split("_")[1]
    
    if os.environ.get("METADATA_URL"):
        metadata_url = os.environ("METADATA_URL")
    
    else:
        metadata_url = "https://raw.githubusercontent.com/ioos/ncei-archiving-cookbook/refs/heads/gh-pages/_docs/files/HFRNet_ERDDAP_Station_Metadata_Lookup_Table.csv"
    
    radials_meta = pd.read_csv(metadata_url)
    
    try:
        operator = radials_meta.loc[radials_meta['Station_ID'] == site.upper()]['Network'].iloc[0]
    except:
        operator = ""
    fname_without_extension = os.path.splitext(_fpath)[0]
    if use_extension is None:
        extension = os.path.splitext(_fpath)[1]
    else:
        extension = use_extension
    # Append the origin location to the file name if supplied
    if (metadata["origin_lon"], metadata["origin_lat"]) == (None, None):
        _fpath_orloc = "{}{}".format(fname_without_extension, extension)
    else:
        _fpath_orloc = "{}_{}_{}{}".format(fname_without_extension,
                                           metadata["origin_lon"],
                                           metadata["origin_lat"], extension)
    cleaned_fpath = _fpath_orloc.replace(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_fpath_orloc)))),
            processed_root
        )
    dataset_id = f"{operator}_{site.upper()}"
    cleaned_fpath  = re.sub(f"{site}_",f"{operator}_{site}_",cleaned_fpath, flags=re.IGNORECASE)
    if cleaned_fpath.startswith("s3://"):
        return cleaned_fpath, dataset_id
    else:
        return os.path.abspath(cleaned_fpath), dataset_id

def get_metadata_from_file(f):
    """Open an ASCII file and parse out its metadata from the header.
    :param str fp: file path
    :return dict"""
    #with open(path, 'r', encoding='utf-8', errors="replace") as f:
    comments = itertools.takewhile(lambda s: s.startswith(b'%'), f)
    comments = list(map(lambda l: l[1:].strip(), comments))
    metadata = {}
    for c in comments:
        if not c.startswith(b'%'):
            metadata_entry = list(map(bytes.strip, c.split(b':')))
            try:
                metadata[metadata_entry[0]] = pd.to_numeric(metadata_entry[1])
            except:
                if len(metadata_entry) >= 2:
                    metadata[metadata_entry[0]] = metadata_entry[1]
    return metadata

def calc_max_range(metadata):
    """Latest implementation of calc_max_range, used with numeric metadata.
    Based on information in the metadata (if available), calculate the maximum
    range of the file.
    :param dict metadata"""

    max_range_arr = np.array([60, 125, 250, 500])

    if (not 'TransmitCenterFreqMHz' in metadata) and ('RangeEnd' in metadata) and ('RangeResolutionKMeters' in metadata):
        max_calc_range = metadata['RangeEnd'] * metadata['RangeResolutionKMeters']
        next_range_indx = np.argwhere(max_range_arr > max_calc_range).min()
        _max_range = max_range_arr[next_range_indx]
    elif ('TransmitCenterFreqMHz' in metadata):
        _max_range = 2000. / metadata['TransmitCenterFreqMHz']
    else:
        _max_range = max_range_arr.max()

    return _max_range

def get_range_res_start_end(metadata):
    """Function to get the range start, end, and resolution in kilometers
    or meters from the metadata.
    :param dict metadata"""

    range_start = metadata.get('RangeStart', None)
    range_end = metadata.get('RangeEnd', None)
    range_resolution_kmeters = metadata.get('RangeResolutionKMeters', None)
    range_resolution_meters = metadata.get('RangeResolutionMeters', None)
    return (range_start, range_end, range_resolution_kmeters, range_resolution_meters)

def get_range_resolution_precision(range_resolution_kmeters, range_resolution_meters):
    """Get the precision of the range resolution by taking the length of resolution string
    split on the decimal.
    :param str range_resolution_kmeters, range_resolution_meters
    :return int range_resolution_kmeters_decimal_digits"""

    # TODO add else? raise Exception?
    if range_resolution_kmeters:
        return len(str(range_resolution_kmeters).split('.')[-1])
    elif range_resolution_meters:
        return len(str(range_resolution_meters).split('.')[-1])

def create_time(metadata):
    """From information in the metadata dict, create a datetime object.
    :param dict metadata
    :return datetime.datetime"""

    return datetime.datetime(*list(map(int, metadata['TimeStamp'].split())))

def create_initial_dataframe(path, metadata, TIME_VAR_STR, time):
    """Use pandas to read in a file and create a DataFrame object.
    Set the column "TIME_VAR_STR" as `time`, a passed datetime object.
    :param str path: path to file
    :param dict metadata
    :param datetime.datetime time
    :return pandas.DataFrame"""

    # create dataframe as it is created in the main function
    df = pd.read_csv(
        path,
        header=None,
        sep=r'\s+',
        comment='%',
        encoding='ascii',
        names=[header_name.decode("utf-8") for header_name in
               metadata[b'TableColumnTypes'].split()]
    )

    df[TIME_VAR_STR] = time
    return df

def get_range_cells(metadata, df, _max_range, range_resolution_kmeters):
    """Return the number of range cells if present in the metadata. If not,
    calculate them based on the calculated maximum range and range resolution in
    kilometers.
    :param dict metadata
    :param pandas.Dataframe df
    :param int _max_range
    :param float range_resolution_kmeters"""

    # NOTE this assumes that range_resolution_kmeters is present
    range_cells = metadata['RangeCells'] if 'RangeCells' in metadata else None
    if range_cells:
        # ensure we have more than one unique value before attempting to use isclose
        if len((df['RNGE']/df['SPRC']).unique()) > 1:
            # TODO raise a better exception
            assert np.isclose(*(df['RNGE']/df['SPRC']).unique()) # verify RNGE/SPRC == range_resolution_kmeters everywhere
    else:
        range_cells = int(np.ceil(_max_range/range_resolution_kmeters))

    return range_cells

def get_olat_olon(metadata):
    """Get the origin latitude and longitude values from the metadata and
    convert to floats.
    :param dict metadata
    :return tuple of floats, length 2"""
    return list(map(float, metadata[b'Origin'].split())) if b'Origin' in metadata else (None, None)

def get_angular_resolution(metadata):
    """Get angular resolution from the metadata.
    :param dict metadata
    :return tuple of floats or None, legnth 2"""
    return float(metadata['AngularResolution'].split()[0]) if 'AngularResolution' in metadata else None # assumes 'X Deg'

def get_antenna_bearing(metadata):
    """Get the antenna bearing from the metadata and convert to float.
    :param dict metadata
    :return float"""

    return float(metadata['AntennaBearing'].split()[0]) if 'AntennaBearing' in metadata else None

def reindex_df_by_lat_lon(df, olat, olon, _max_range, TIME_VAR_STR, time):
    """Create a MultiIndex from the time, latitude and longitude values.
    :param pandas.DataFrame df
    :param float/None olat, olon
    :param int _max_range
    :param datetime.datetime time
    :return pandas.DataFrame"""

    # get unique lats/lngs
    unique_lats = np.unique(df['LATD']).round(7)
    unique_lons = np.unique(df['LOND']).round(7)

    # get min diff of unique lats/lons
    min_lat_diff = np.min(np.diff(unique_lats))
    min_lon_diff = np.min(np.diff(unique_lons))

    calculated_lat_slot = [int(i) for i in list(np.floor((df['LATD']-np.min(unique_lats))/min_lat_diff))]
    calculated_lon_slot = [int(i) for i in list(np.floor((df['LOND']-np.min(unique_lons))/min_lon_diff))]

    # add new columns to existing dataframe
    df['j'] = calculated_lat_slot
    df['i'] = calculated_lon_slot

    df = df.set_index([TIME_VAR_STR, 'i', 'j'])

    # calcuate max lat/lng extents based on bearing & range to calcuate theoretical number of lat/lon slots
    _, min_lat = _rb2ll(olon,olat,_max_range,180)
    _, max_lat = _rb2ll(olon,olat,_max_range,0)
    min_lon, _ = _rb2ll(olon,olat,_max_range,270)
    max_lon, _ = _rb2ll(olon,olat,_max_range,90)

    theoretical_max_lat_slot = np.int(np.ceil((max_lat-np.min(unique_lats))/min_lat_diff))
    theoretical_max_lon_slot = np.int(np.ceil((max_lon-np.min(unique_lons))/min_lon_diff))

    lat_slots = np.arange(theoretical_max_lat_slot)
    lon_slots = np.arange(theoretical_max_lon_slot)

    df = df.reindex(pd.MultiIndex.from_product([[time], lon_slots, lat_slots], names=df.index.names))

    return df

def reindex_df_by_range_bearing(df, angular_resolution,
    range_resolution_kmeters_decimal_digits, range_resolution_kmeters,
    _max_range, range_cells, TIME_VAR_STR, time):
    """Reindex the DataFrame by creating a MultiIndex of ranges and bearings.
    :param pandas.DataFrame df
    :param float/None angular_resolution
    :param int range_resolution_kmeters_decimal_digits
    :param float range_resolution_kmeters
    :param float _max_range
    :param int range_cells
    :param str TIME_VAR_STR
    :param datetime.datetime time
    :return pandas.DataFrame"""

    # TODO should raise more explicit errors

    unique_bearing_diffs = np.diff(np.unique(df['BEAR']))

    df = df.set_index([TIME_VAR_STR, 'BEAR', 'RNGE'])

    # deal with missing angular resolution metadata
    if not angular_resolution:
        angular_resolution = unique_bearing_diffs.min() # just pick the first one

    # ranges
    assert all((np.unique(np.diff(df.index.get_level_values('RNGE')).round(decimals=range_resolution_kmeters_decimal_digits)) // range_resolution_kmeters) % 1. == 0)
    _rmin = df.index.get_level_values('RNGE').unique().min() # min/max ranges we see
    _rmax = df.index.get_level_values('RNGE').unique().max()

    all_ranges = np.unique(np.concatenate((
        (np.arange(_rmin, 0,    -range_resolution_kmeters)[1:][::-1]),
        (np.arange(_rmin, _rmax, range_resolution_kmeters)), # dont include last element (fixed issue here)
        (np.arange(_rmax, _max_range+0.01, range_resolution_kmeters))
    )).round(decimals=range_resolution_kmeters_decimal_digits)[:range_cells])

    # bearings
    assert all(unique_bearing_diffs % angular_resolution == 0)
    _bmin = df.index.get_level_values('BEAR').unique().min() # min/max bearings we see
    _bmax = df.index.get_level_values('BEAR').unique().max()


    all_bearings = np.unique(np.concatenate((
        (np.arange(_bmin, 0, -angular_resolution)[1:][::-1]),
        (np.arange(_bmin, _bmax, angular_resolution)),
        (np.arange(_bmax, 360.1, angular_resolution))
    )))

    df = df.reindex(pd.MultiIndex.from_product([[time], all_bearings, all_ranges], names=df.index.names))

    return df

def create_xarray_dataset(df, metadata, TIME_VAR_STR, CF_TIME_UNITS,
    olat, olon, antenna_bearing, TableColumnTypes):
    """Create an XARRAY dataset from a pandas DataFrame and given metadata.
    :param pandas.DataFrame df
    :param dict metadata
    :param str TIME_VAR_STR
    :param str CF_TIME_UNITS
    :param float olat, olon, antenna_bearing
    :param dict TableColumnTypes
    :return xarray.Dataset"""

    ds = xr.Dataset.from_dataframe(df)
    ds.attrs = metadata
    # update `units` for `TIME` variable (for later record concatenation)
    ds[TIME_VAR_STR].encoding.update({'dtype': 'float64', 'units': CF_TIME_UNITS})
    # add scalar variables
    ds['OLAT'] = ([TIME_VAR_STR], [olat])
    ds['OLON'] = ([TIME_VAR_STR], [olon])
    # AntennaBearing
    ds['ANTB'] = ([TIME_VAR_STR], [antenna_bearing])

    # add variable attributes from TableColumnTypes
    for k,v in TableColumnTypes.items():
        if k in ds:
            ds[k].attrs.update({'long_name': v})

    return ds
