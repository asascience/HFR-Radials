FROM ubuntu:22.04
    
RUN apt update && apt install -y python3-pip python3-dev netcdf-bin libhdf5-dev libnetcdf-dev git && \
           apt clean && rm -rf /var/cache/apt &&  \
    cd /usr/local/bin && \
    ln -s /usr/bin/python3 python 

# add user and group
RUN groupadd ott_user_group && \
    useradd -G ott_user_group ott_user


# copy directory contents, install requirements and module
COPY . /srv
WORKDIR /srv
RUN pip install  -r requirements.txt

# set user and group
USER ott_user


# invoke script to kick off the real-time ingest process
# the path to the configuration JSON (should match the directory
# of the data directories, plus '/config/realtime_cfg.json')
ENTRYPOINT ["/usr/local/bin/python", "-m", "awslambdaric"]
CMD ["hfr_wave.lambda_handler"]
