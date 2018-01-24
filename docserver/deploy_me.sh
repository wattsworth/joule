#!/bin/bash

ng build --env prod --prod --base-href=/modules/
rsync -r --delete dist/ portal.wattsworth.net:/var/www/docs/modules
ssh portal.wattsworth.net ./update_doc_tarball.sh
