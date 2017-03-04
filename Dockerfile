FROM ubuntu:xenial

MAINTAINER Oliver Steele <steele@osteele.com>

ENV DEBIAN_FRONTEND noninteractive

# install Python, git, sqlite3, and postgresql
RUN apt-get update -y
RUN apt-get install -y python3-pip python3-dev build-essential
RUN apt-get install -y git-core
RUN apt-get install -y sqlite3 libsqlite3-dev
RUN apt-get install -y postgresql libpq-dev

# provide cached layer for expensive requirements, beneath requirements.txt
RUN pip3 install nbconvert nbformat numpy pandas

# provide cached layer for requirements, beneath rest of sources
WORKDIR /app
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
