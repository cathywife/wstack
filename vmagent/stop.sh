#!/bin/bash

ps -ef |grep agent.py |grep -v grep |awk '{print $2}' |xargs sudo kill
