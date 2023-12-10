FROM wattsworth/joule:latest
LABEL John Donnal <donnal@usna.edu>

# install tools for testing
RUN apt-get update && \
    apt-get install -y postgresql\
    && rm -rf /var/lib/apt/lists/*

COPY . /joule
RUN cd /joule && pip install .
RUN pip install coverage

CMD tests/e2e/bootstrap_inner.sh timescale tests/e2e/follower_node.py