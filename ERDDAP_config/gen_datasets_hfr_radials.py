'''
Created on Dec 20, 2019

@author: cheryl.morse
'''

import pandas as pd

if __name__ == '__main__':
    radials = "radials"
    waves = "waves"
    outputFile = "datasets_prod.xml"
    template_dir = "./templates"
   
    with open(f"{template_dir}/radials_header.xml", "r", encoding="utf-8") as source:
       header_content = source.read()

    with open(f"{template_dir}/erddap_tail.xml", "r", encoding="utf-8") as source:
       tail_content = source.read()

    with open(outputFile,'w+') as out:
        out.write(header_content)
        for data_type in [radials, waves]:
            
            if data_type == radials:
                struct_file = f"{template_dir}/radials_template_s3.xml"
            else:
                struct_file = f"{template_dir}/radials_wave_s3.xml"
                wave_files = ['BIGC','BRMR','CMPT','FORT','FRDO','GCYN','HLGT','MBAC', 'MONT','PILR','PSLR','SBAY','SCRZ','SEAB','SILD','SPRK','WSH1', 'WLD2','WOOD','SOB2'] 
            
            radials_meta = pd.read_csv("https://raw.githubusercontent.com/ioos/ncei-archiving-cookbook/refs/heads/gh-pages/_docs/files/HFRNet_ERDDAP_Station_Metadata_Lookup_Table.csv")
        
    
            for index, station_meta  in radials_meta.iterrows():
                station=station_meta ['Station_ID']
                
                if data_type == waves: 
                    if station not in wave_files: continue
                    
                       
                institution=station_meta ['Network']
                        #station_meta = radials_meta.loc[radials_meta['Station_ID']==station]
                data_rep_keys={
                            '#STATION#':station,
                            '#INSTITUTION#': institution}
          
                meta_data_rep_keys = {"#CREATOR_TYPE#":"creator_type",
                                      "#CREATOR_INST#":"creator_institution",
                                      "#CREATOR_NAME#":"creator_name",
                                      "#CREATOR_EMAIL#":"creator_email",
                                      "#CREATOR_URL#":"creator_url",
                                      "#CREATOR_COUNTRY#":"creator_country",
                                      "#CREATOR_SECTOR#":"creator_sector",
                                      "#PLATFORM_NAME#":"platform_name"}
     
                with open(struct_file) as temp:
                    for line in temp:
                    
                        for meta_key in data_rep_keys:
                            if meta_key in line:
                                line = line.replace(meta_key, data_rep_keys[meta_key])
        
                                
                        for meta_key in meta_data_rep_keys:
                            if meta_key in line:
                                line = line.replace(meta_key, station_meta[meta_data_rep_keys[meta_key]])
                        if '&' in line:
                            line =line.replace("&","&amp;") 
                        out.write(line)
        out.write(tail_content)    
