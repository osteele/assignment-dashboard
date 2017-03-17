FROM python:3.6

MAINTAINER Oliver Steele <steele@osteele.com>

ENV DEBIAN_FRONTEND=noninteractive

COPY Aptfile /tmp/
RUN apt-get update \
  && (egrep -v '#|^$' /tmp/Aptfile | xargs apt-get install --no-install-recommends -y) \
  && apt-get autoremove -y \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV PYTHONDONTWRITEBYTECODE=1

RUN pip3 install --upgrade pip==9.0.1

# provide cached layer for requirements, beneath rest of sources
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
COPY . /app/
RUN python setup.py develop

ENV FLASK_APP=assignment_dashboard

HEALTHCHECK CMD curl --fail http://localhost:5000/health || exit 1

EXPOSE 5000

ENTRYPOINT ["flask"]
CMD ["run", "--host", "0.0.0.0"]
