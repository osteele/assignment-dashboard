FROM assignment-dashboard

MAINTAINER Oliver Steele <steele@osteele.com>

RUN apt-get install -y cron

COPY cron-python /etc/cron.d/
RUN chmod 0644 /etc/cron.d/cron-python

RUN mkdir /worker
COPY update-db /worker
RUN chmod +x /worker/update-db

ENTRYPOINT ["/bin/bash"]
CMD ["-c", "env > /worker/.env && cron -f"]
