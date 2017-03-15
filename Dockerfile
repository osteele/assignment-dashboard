FROM python:3.6

MAINTAINER Oliver Steele <steele@osteele.com>

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update -y

WORKDIR /app
COPY Aptfile /app/Aptfile
# Spur the best practice to rm the apt-get files,
# in order to make this quicker to iterate with at the expense of
# image size.
RUN egrep -v '#|^$' /app/Aptfile \
    | xargs apt-get -y --no-install-recommends install

RUN pip3 install --upgrade pip==9.0.1

# provide cached layer for requirements, beneath rest of sources
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . /app
RUN python setup.py develop

# Flask requires this
ENV FLASK_APP=assignment_dashboard

HEALTHCHECK CMD curl --fail http://localhost:5000/health || exit 1

EXPOSE 5000

ENTRYPOINT ["flask"]
CMD ["run", "--host", "0.0.0.0"]
