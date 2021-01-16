.PHONY: lint next-version accept-version revoke-version

# Setup
VERSION=0.3.3
SOURCE_PATH=./apps
DOCKER_REPO=hazard
IMAGE_NAME=$(DOCKER_REPO)/appdaemon-apps
FULL_IMAGE_NAME=$(IMAGE_NAME):$(VERSION)
FULL_IMAGE_NAME_ARM=$(IMAGE_NAME):$(VERSION)-arm

# Environment overrides
VERSION_PART?=patch

setup:
	pip install pip --upgrade
	pip install -r requirements.txt --upgrade

lint:
	flake8 --exclude=.tox --max-line-length 120 --ignore=E722 $(SOURCE_PATH)

docker:
	docker build -t $(FULL_IMAGE_NAME) -f Dockerfile .

docker-arm:
	docker build -t $(FULL_IMAGE_NAME_ARM) -f Dockerfile.armhf .

docker-push: docker
	docker push $(FULL_IMAGE_NAME)
	docker tag $(FULL_IMAGE_NAME) $(IMAGE_NAME):latest
	docker push $(IMAGE_NAME):latest

docker-push-arm: docker-arm
	docker push $(FULL_IMAGE_NAME_ARM)
	docker tag $(FULL_IMAGE_NAME_ARM) $(IMAGE_NAME):latest-arm
	docker push $(IMAGE_NAME):latest-arm

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
