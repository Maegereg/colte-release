#! /usr/bin/env python3

""" This module builds all of the components in the colte ecosystem according to
specific tag versions for each component.

It attempts to only use python3 standard library functions for portability, but
assumes the host system has python3 and has access to git on the user PATH.
"""

from collections import namedtuple
from pathlib import Path

import argparse
import logging
import os
import shutil
import subprocess

Repo = namedtuple("Repo", ["local_path", "url"])
REPOS = [
    Repo(local_path="colte", url="https://github.com/uw-ictd/colte.git"),
]

DISTRIBUTIONS = ["buster", "bionic", "focal"]

def _checkout_repo(workspace_path, repo, ref_label):
    """ Check out a given ref_label at local path, respecting existing repos.

    This assumes if a directory is already present at the desired path, that it
    is an earlier version of the correct git repo.
    """
    local_path = workspace_path.joinpath(Path(repo.local_path))

    if not local_path.exists():
        # If the repo isn't already cloned, clone it fresh.
        subprocess.run(["git", "clone", repo.url, local_path], check=True)
    else:
        # Otherwise do a fetch to get the latest refs
        subprocess.run(["git", "fetch", "origin"], cwd=local_path, check=True)

    # Checkout the appropriate ref
    subprocess.run(["git", "checkout", ref_label], cwd=local_path, check=True)

def _setup_workspace(workspace_path):
    """ Setup a barebones workspace with the correct directory structure and files.
    """
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Make a directory to bind mount into the containers for output
    Path(workspace_path.joinpath("build-volume")).mkdir(parents=True, exist_ok=True)

    # Copy needed files from this repo into the workspace
    shutil.copy(Path("docker/docker-entrypoint.sh"), workspace_path.joinpath(Path("docker-entrypoint.sh")))

def _build_docker_image(base_build_path, dockerfile, image_tag):
    subprocess.run(["docker", "build", "-f", dockerfile, "--tag", image_tag, base_build_path])

def _run_dockerized_build(workspace_path, image_tag):
    host_bind_path = workspace_path.joinpath("build-volume").resolve()

    subprocess.run(
        ["docker",
         "run",
         "-v",
         "{}:/build-volume".format(str(host_bind_path)),
         image_tag,
         str(os.getuid())
         ])

def main(workspace_path):
    parser = argparse.ArgumentParser()
    specifier_group = parser.add_mutually_exclusive_group(required=True)
    specifier_group.add_argument("--tag", help="The tag to build")
    specifier_group.add_argument("--main", action="store_true", help="Build the latest main branch")
    parser.add_argument("--clean", action="store_true", help="Force a clean build, removing existing intermediates")
    args = parser.parse_args()
    log.debug("Parsed args {}".format(args))

    if args.main:
        ref_label = "master"
    else:
        ref_label = args.tag

    if args.clean:
        if workspace_path.exists():
            log.warning("Removing existing tree at '{}' due to clean request".format(workspace_path.resolve()))
            shutil.rmtree(workspace_path)
        else:
            log.info("Clean requested, but no clean to do for path '{}'".format(workspace_path.resolve()))

    _setup_workspace(workspace_path)

    for repo in REPOS:
        _checkout_repo(workspace_path=workspace_path, repo=repo, ref_label=ref_label)

    for distro in DISTRIBUTIONS:
        image_name = "colte/{}-build-local".format(distro)
        _build_docker_image(
            workspace_path,
            Path("docker/Dockerfile-{}".format(distro)),
            image_tag=image_name,
        )
        _run_dockerized_build(workspace_path, image_tag=image_name)

if __name__ == "__main__":
    logging.basicConfig()
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)

    main(workspace_path=Path("scratch/"))

    logging.shutdown()