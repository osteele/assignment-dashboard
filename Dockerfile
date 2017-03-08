FROM python:3.6

MAINTAINER Oliver Steele <steele@osteele.com>

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update -y

WORKDIR /app
COPY Aptfile /app/Aptfile
RUN egrep -v '#|^$' /app/Aptfile | xargs apt-get -y --force-yes install

RUN pip3 install --upgrade pip

# provide cached layer for expensive requirements, beneath requirements.txt
COPY requirements-cached.txt /app/requirements-cached.txt
RUN pip3 install -r requirements-cached.txt

# provide cached layer for requirements, beneath rest of sources
COPY requirements.txt /app/requirements.txt
RUN pip3 install -r requirements.txt

COPY . /app
RUN pip3 install -e .

# required by Flask and Python 3 respectively
ENV FLASK_APP=assignment_dashboard
ENV LC_ALL=C.UTF-8 LANG=C.UTF-8

EXPOSE 5000

ENTRYPOINT ["flask"]
CMD ["run", "--host", "0.0.0.0"]
