#!/bin/bash

cloc --exclude-list-file .clocignore --exclude-lang "SVG,XML,DOS Batch,MATLAB,Dockerfile,Markdown,diff,YAML,SQL,HTML,make" .
