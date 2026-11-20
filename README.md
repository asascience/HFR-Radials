# HFR-Radials
From the SOW: Tetra Tech will operate, maintain, and enhance the ERDDAP server that hosts coastal high-frequency radar (HFR) radial velocity and wave (height, period, and direction) data for the IOOS HFR National Network. 

IOOS HFR Radials ERDDAP
Configuration, ingestion, and recovery documentation for the IOOS High-Frequency Radar (HFR) ERDDAP service.

The service provides public access to real-time and historical HFR radial surface-current velocity data and associated wave datasets. This repository is intended to preserve the configuration and supporting materials needed to understand, maintain, and recover the service.

Repository status: Confirm that the files in this repository match the configuration currently deployed in production before using them for recovery or making production changes. The authoritative production configuration location has not yet been confirmed.

Service
ERDDAP landing page: https://hfradar.ioos.us/erddap/index.html
Purpose: Provide standard, public access to HFR radial observations and hosted wave datasets for research, operations, and downstream applications.
Upstream data: Radial and wave data are ingested from available IOOS HFR National Network data sources, including NOAA NESDIS Common Cloud Framework (NCCF) distribution services.
Potential extension: Prototype access to NCCF real-time vector (RTV) products through ERDDAP. RTV is gridded total surface-current velocity data derived from radial observations; its inclusion is an investigation/prototype, not a production capability guaranteed by this repository.

Repository contents
Expected files may include:

Path or file	Purpose
datasets.xml	ERDDAP dataset definitions and related metadata.
setup.xml	ERDDAP server configuration. Review carefully before sharing; remove secrets and environment-specific values.
scripts/	Ingestion, processing, validation, or maintenance scripts, where applicable.
docker-compose.yml	Container service definitions, if confirmed to be part of the supported deployment.
docs/	Setup, operations, recovery, and data-flow documentation.
examples/	Sanitized examples that do not contain credentials or sensitive operational details.
The list above is a suggested structure, not confirmation that every file is present or currently used in production. Document the role and provenance of each committed configuration file.

Data and standards
ERDDAP datasets should retain accurate, discoverable metadata and support appropriate data access services. As applicable, configuration and datasets should follow:

Climate and Forecast (CF) Metadata Conventions
Attribute Convention for Data Discovery (ACDD)
IOOS data publishing guidance

Configuration and deployment notes
The project notes refer to a Docker-based ERDDAP deployment and list several possible locations for docker-compose.yml. Those paths have not been confirmed as the authoritative production source. Do not treat a path mentioned in project notes as a verified deployment instruction.

Before changing or restoring production:

Confirm the current production host, deployment method, and authoritative configuration paths with the project maintainers.
Confirm that the repository revision matches the deployed configuration and identify any intentional differences.
Review environment variables, mounted volumes, file permissions, and external data dependencies.
Back up the current configuration and relevant operational state.
Test changes in a non-production environment where possible.
Follow the approved operational process for production changes and service restarts.
This repository intentionally does not document server credentials, private keys, access tokens, or other secrets. Use approved secret-management and access-control procedures.

Recovery
Use this repository as one part of a recovery process—not as a complete backup of the production service. Recovery may also depend on data files, storage, container images, environment-specific settings, network access, and upstream NCCF services.
