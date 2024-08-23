# lint
pytype streaming_status alarms_router
# format
autoflake -ri --remove-all-unused-imports --ignore-init-module-imports ./streaming_status ./alarms_router
isort ./streaming_status ./alarms_router
black -t py37 ./streaming_status ./alarms_router
sort -o .gitignore .gitignorej