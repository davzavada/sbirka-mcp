ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1

# Install the sbirka-mcp package straight from the repository (no git needed —
# pip installs from the GitHub source tarball). Rebuild the add-on to pull the
# latest version of main.
RUN pip install --no-cache-dir \
    "https://github.com/davzavada/sbirka-mcp/archive/refs/heads/main.tar.gz"

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
