
SHELL := /bin/bash
SCRIPTS := scripts
TMPLOG := tmp/logs
LOGFILE := $(TMPLOG)/app.log

.PHONY: setup test-rotate rotate backup health clean

setup:
	mkdir -p $(TMPLOG) backups
	@echo "setup done"

$(LOGFILE):
	mkdir -p $(TMPLOG)
	for i in {1..200}; do echo "$$(date) sample log $$i" >> $(LOGFILE); done

test-rotate: $(LOGFILE)
	bash $(SCRIPTS)/log_rotator.sh "$(TMPLOG)/*.log" 3
	@echo "gz files:"; ls -1 $(TMPLOG)/*.gz || true

rotate:
	bash $(SCRIPTS)/log_rotator.sh "$(TMPLOG)/*.log" 5

backup:
	bash $(SCRIPTS)/backup.sh . backups

health:
	bash $(SCRIPTS)/healthcheck.sh || true

clean:
	rm -rf backups $(TMPLOG)
