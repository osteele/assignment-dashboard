FROM assignment-dashboard:latest

MAINTAINER Oliver Steele <steele@osteele.com>

RUN apt-get install -y --no-install-recommends cron

COPY cron-updatedb /etc/cron.d/
RUN chmod 0644 /etc/cron.d/cron-updatedb

RUN mkdir /worker
COPY updatedb /worker

RUN touch /var/log/updatedb.log

ENTRYPOINT ["/bin/bash"]
CMD ["-c", "env > /worker/.env && cron && tail -f /var/log/updatedb.log"]
