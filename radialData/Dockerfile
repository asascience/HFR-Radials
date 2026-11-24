FROM ubuntu:22.04
    
RUN apt update && apt install -y python3-pip python3-dev netcdf-bin libhdf5-dev libnetcdf-dev git && \
           apt clean && rm -rf /var/cache/apt &&  \
    cd /usr/local/bin && \
    ln -s /usr/bin/python3 python 

# add user and group
RUN groupadd ott_user_group && \
    useradd -G ott_user_group ott_user

# make data directories; this is where data will reside and
# will be mounted at runtime
RUN mkdir -p /data/config

# copy directory contents, install requirements and module
COPY . /srv
WORKDIR /srv
RUN pip install --no-cache -r requirements.txt

# change ownership of log directories, AWS creds, OUTPUT, and config
RUN chown -R ott_user /srv/ && chgrp -R ott_user /srv/ 

# set user and group
USER ott_user


# invoke script to kick off the real-time ingest process
# the path to the configuration JSON (should match the directory
# of the data directories, plus '/config/realtime_cfg.json')
ENTRYPOINT ["/usr/local/bin/python", "-m", "awslambdaric"]
CMD ["hfr_radial.lambda_handler"]
