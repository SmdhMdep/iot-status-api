# SMDH IoT Hub Devices Status API

This API exposes three endpoints:

- /api/devices - list all devices for the provider
- /api/devices/export - export a list of all devices into csv or json
- /api/devices/<device_id> - get device details
- /api/providers - for admins, list all device providers

## Configuration

Use the template [`example.env`](./example.env) to create a `<stage>.env` file with populated values.
For example, create a `dev.env` file for the dev stage.

In prod stage a custom authorizer shared by multiple projects is used. However, in dev stage
a JWT authorizer is configured using the configuration from the environment file.

## Deployment

```sh
sls deploy --stage <stage>
```

## Local development

During development, the AWS credentials will be based on the current environment.

An optional `provider` query parameter can be passed to each endpoint, which will be used instead of using token inspection, thus eliminating the need for authenticating.

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
