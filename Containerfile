# Use UBI9 as the base image
FROM registry.access.redhat.com/ubi9-minimal

RUN microdnf install -y python3.11 python3.11-pip git && \
    microdnf clean all && \
    git clone https://github.com/rhtools/mtv-parser && \
    cd mtv-parser && \
    git checkout dev && \
    pip3.11 install -r requirements.txt 

VOLUME ["mtv_parser/charts"]

USER 1001

WORKDIR /mtv-parser
CMD ["python3.11", "mtv_parser/mtv_plan_parser.py"]
