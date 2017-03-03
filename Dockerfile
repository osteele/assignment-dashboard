FROM ubuntu:xenial
MAINTAINER Oliver Steele "steele@osteele.com"

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update -y
RUN apt-get install -y --force-yes python3-pip python3-dev build-essential
RUN apt-get install -y --force-yes git-core
RUN apt-get install -y --force-yes sqlite3 libsqlite3-dev
RUN apt-get install -y --force-yes postgresql libpq-dev

# nbconvert requires these. installing it installs them, but
# hoist them up here so that changes to the app can build on
# this cached layer.
RUN pip3 install nbconvert nbformat numpy

# from requirements.txt; hoisted to cache
RUN pip3 install pandas

WORKDIR /app

# first copy just the requirements
COPY requirements.txt /app/requirements.txt
RUN pip3 install -r requirements.txt

COPY . /app
RUN pip3 install -e .

ENV FLASK_APP=assignment_dashboard

ENV LC_ALL=C.UTF-8 LANG=C.UTF-8

EXPOSE 5000

ENTRYPOINT ["flask"]
CMD ["run", "--host", "0.0.0.0"]
