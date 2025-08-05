#!/bin/bash
CMD=$1
shift

# FIXME set this value
export GOOGLE_CLOUD_PROJECT=sample

case $CMD in
run)
	python3 $HOME/google-cloud-sdk/bin/dev_appserver.py app.yaml -A $GOOGLE_CLOUD_PROJECT --skip_sdk_update_check=yes --port=9999 --admin_port=8113 --enable_console --host=0.0.0.0 --log_level=debug --enable_host_checking False --python_virtualenv_path ../pyenv $*
	;;

deploy)
	gcloud app deploy app.yaml --project $GOOGLE_CLOUD_PROJECT --version live $*
	;;

*)
	echo "$0 [run|deploy]"
	echo
	echo "Examples:"
	echo "$0 run"
	echo "$0 deploy"
	;;
esac
