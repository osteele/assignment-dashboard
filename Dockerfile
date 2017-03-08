FROM python:3.6

MAINTAINER Oliver Steele <steele@osteele.com>

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update -y
RUN pip3 install --upgrade pip

WORKDIR /app
COPY Aptfile /app/Aptfile
RUN egrep -v '#|^$' /app/Aptfile | xargs apt-get -y --force-yes install

# provide cached layer for requirements, beneath rest of sources
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . /app
RUN pip3 install --no-cache-dir -e .

# Flask requires this
ENV FLASK_APP=assignment_dashboard

EXPOSE 5000

ENTRYPOINT ["flask"]
CMD ["run", "--host", "0.0.0.0"]
