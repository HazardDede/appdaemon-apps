.PHONY: lint next-version accept-version revoke-version

# Setup
VERSION=0.1.0
SOURCE_PATH=./apps
CONTAINER_NAME=appdaemon

# Environment overrides
VERSION_PART?=patch

setup:
	pip install pip --upgrade
	pip install -r requirements.txt --upgrade

lint:
	flake8 --exclude=.tox --max-line-length 120 --ignore=E722 $(SOURCE_PATH)

docker:
	docker build -t $(CONTAINER_NAME):$(VERSION) -f Dockerfile .

docker-arm:
	docker build -t $(CONTAINER_NAME):$(VERSION)-arm -f Dockerfile.armhf .

version:
	@echo $(VERSION)

next-version: lint
	$(eval NEXT_VERSION := $(shell bumpversion --dry-run --allow-dirty --list $(VERSION_PART) | grep new_version | sed s,"^.*=",,))
	@echo Next version is $(NEXT_VERSION)
	bumpversion $(VERSION_PART)
	@echo "Review your version changes first"
	@echo "Accept your version: \`make accept-version\`"
	@echo "Revoke your version: \`make revoke-version\`"

accept-version:
	git push && git push --tags

revoke-version:
	git reset --hard HEAD~1                        # rollback the commit
	git tag -d `git describe --tags --abbrev=0`    # delete the tag
