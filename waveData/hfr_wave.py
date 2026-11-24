
import sys
import s3fs
import re
import os
import json
import datetime
import requests
import pandas as pd
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
            process_wave_file(s3_file_location)
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
            
def process_wave_file(file_c):
    if os.environ.get("PROCESSED_ROOT"):
        out_bucket = os.environ["PROCESSED_ROOT"]
    else:
        out_bucket = "rps-nccf-hfrnet-processed-uat"
        
    station = os.path.basename(file_c).split("_")[1]    
        
        
    if os.environ.get("METADATA_URL"):
        metadata_url = os.environ("METADATA_URL")
    
    else:
        metadata_url = "https://raw.githubusercontent.com/ioos/ncei-archiving-cookbook/refs/heads/gh-pages/_docs/files/HFRNet_ERDDAP_Station_Metadata_Lookup_Table.csv"
    
    radials_meta = pd.read_csv(metadata_url)
    
    try:
        operator = radials_meta.loc[radials_meta['Station_ID'] == station.upper()]['Network'].iloc[0]
    except:
        operator = ""    

    s3_sub_loc = file_c.split("waves/")[-1]
    sub_split = s3_sub_loc.split("/")
    s3_sub_loc = f"{sub_split[0]}/{sub_split[-1]}"
    s3_f = f"{out_bucket}/waves/{s3_sub_loc.replace('wls','csv')}"
    print(s3_f)
    s3_f = re.sub(f"{station}_",f"{operator}_{station}_",s3_f, flags=re.IGNORECASE)
    #print(s3_f)
    #print(station, operator)
    fs = s3fs.S3FileSystem(anon=False)
    with fs.open(file_c, "r") as f:
        with fs.open(s3_f ,"w") as out_f:
            for l in f.readlines():
                if ("%TableColumnTypes:" in l):
                    header = l.split("%TableColumnTypes:")[1].strip()
                    out_f.write(f"TIME_SEC,{header.replace(' ',',')}\n")
                    header_sp = header.split(" ")
                    tyr = header_sp.index("TYRS")
                    tmon = header_sp.index("TMON")
                    tday = header_sp.index("TDAY")
                    thrs = header_sp.index("THRS")
                    tmin = header_sp.index("TMIN")
                    tsec = header_sp.index("TSEC")
                    
                elif l[0] !="%":
                    out_line = re.sub(' +', ' ',l.strip())
                    out_s = out_line.split()
                    #time_s = f"{out_s[tyr]}-{out_s[tmon]}-{out_s[tday]}T{out_s[thrs]}:{out_s[tmin]}:{out_s[tsec]}Z"
                    time_dt = datetime.datetime(int(out_s[tyr]),int(out_s[tmon]),int(out_s[tday]),int(out_s[thrs]),int(out_s[tmin]),int(out_s[tsec]))
                    #print(f"{time_dt.timestamp()}" )
                    out_f.write(f"{time_dt.timestamp()},{out_line.replace(' ',',')}\n")
                    #out_f.write(f"{time_s},{out_line.replace(' ',',')}\n")
    if os.environ.get("UPDATE_ERDDAP_SERVICE"):
        service_endpoint = os.environ["UPDATE_ERDDAP_SERVICE"]
    else:
        service_endpoint ="http://3.219.116.209:8091/update_erddap/" 
    requests.get(service_endpoint, {"dataset" :f"{operator}_{station}_hfr_wave"}, headers={'api-key':os.environ["FLAG_API_KEY"]})
            
if __name__ == '__main__':
    process_wave_file(sys.argv[1])
    
    
    
    
