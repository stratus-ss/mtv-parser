# Use UBI9 as the base image
FROM registry.access.redhat.com/ubi9-minimal

RUN microdnf install -y python3.11 python3.11-pip && \
    microdnf clean all

# Copy local code instead of cloning from GitHub
COPY . /mtv-parser/

WORKDIR /mtv-parser

RUN pip3.11 install -r requirements.txt

RUN mkdir -p /mtv-parser/plans/multiple /mtv-parser/charts

VOLUME ["mtv-parser/charts"]
VOLUME ["mtv-parser/plans/multiple"]

USER 1001

WORKDIR /mtv-parser
ENTRYPOINT ["python3.11", "mtv_parser/mtv_plan_parser.py"]
CMD []
