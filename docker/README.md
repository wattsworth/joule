This container is built by CI/CD when a new commit is tagged with a version number.
To build the container locally, run the following command where 0.9.XX is the version number.
This works on Linux but not on OSX. Repeat with the latest tag, not ideal but otherwise
you can only push the local architecture and not the multiarch image.

```bash
docker buildx build --push --platform linux/amd64,linux/arm64 --tag wattsworth/joule:0.10.XX .
```

