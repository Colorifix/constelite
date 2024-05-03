# API

## Intro

API is a component of constelite that exposes protocols and stores to clients. 

Currently constelite has only API, StarliteAPI, which serves protocols and stores over HTTP. 

However, API is an abstract layer and different implementations can be added. For example, we have CamundaAPI in development, which will expose protocols through [zeebe](https://github.com/camunda/zeebe), allowing Camunda engine to execute them.

