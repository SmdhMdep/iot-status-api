# SMDH IoT Hub Devices Status API

This API exposes the following endpoints:

- /api/me - get information about current user including permissions
- /api/me/permissions - list the permissions for the current user
- /api/devices - list all devices for the provider
- /api/devices/export - export a list of all devices into csv or json
- /api/devices/<device_id> - get device details
- /api/providers - list device providers
- /api/organizations - list organizations
- /api/projects - list projects
- /api/schemas - list all devices data schemas
- /api/schemas/<schema_id> - get schema by id

## Getting started

1. Install serverless CLI using `npm install -g serverless`.
2. Install serverless plugins defined in this package by running `npm install`
preferably with the node version specified in `.node-version`.
3. **RECOMMENDED** create a new virtual environment preferably using the python version
specified in `.python-version` file, venv can be used to do so `python -m venv .venv`
(you can change `.venv` with any path you want), and then activate it `source .venv/bin/activate`.
4. Install the requirements/dev.txt requirements file for local development
using `python -m pip install -r requirements/dev.txt`.

## Configuration

Use the template [`example.env`](./example.env) to create a `<stage>.env` file with populated values.
For example, create a `dev.env` file for the dev stage.

In prod stage a custom authorizer shared by multiple projects is used. However, in dev stage
a JWT authorizer is configured using the configuration from the environment file.

The AWS credentials will be based on the current environment.
If you have multiple AWS profiles, you can export the environment variable `AWS_PROFILE`
to specify the profile for development and deployment.

## Local development

In local development, an optional `provider` query parameter can be passed to each endpoint, which will be used instead of using token inspection, thus eliminating the need for authenticating.

You can emulate API Gateway and Lambda locally by using `serverless-offline` plugin. In order to do that, execute the following command:

```sh
sls offline --stage dev --noAuth
```

And then invoke the function, for example, using curl:

```sh
curl "http://localhost:3000/api/devices?provider=smdh"
```

Alternatively, it is also possible to invoke the function locally by using the following command:

```sh
sls invoke local --function devicesStatusApi --stage dev --path event.json
```

In this case you have to provide the full event payload to the function (serverless generate event command
will generate an old format of the event payload which the function cannot handle).

For more info, refer to the serverless and serverless-offline documentations.

## Deployment

```sh
sls deploy --stage <stage>
```
