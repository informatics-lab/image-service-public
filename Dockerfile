FROM quay.io/informaticslab/iris

#poke2
MAINTAINER niall.robinson@informaticslab.co.uk 

ADD . ./

RUN cd ./imageservice && git clone https://github.com/met-office-lab/cloud-processing-config.git config

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ./imageservice/procjob.py
