FROM assignment-dashboard

MAINTAINER Oliver Steele <steele@osteele.com>

COPY cron-updatedb /etc/cron.d/
RUN chmod 0644 /etc/cron.d/cron-updatedb

RUN mkdir /worker
COPY updatedb /worker

RUN touch /var/log/updatedb.log

HEALTHCHECK NONE

ENTRYPOINT ["/bin/bash"]
CMD ["-c", "env > /worker/.env && cron && tail -f /var/log/updatedb.log"]
