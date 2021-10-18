FROM bcgovimages/aries-cloudagent:py36-1.16-1_0.7.1

RUN pip3 install poetry
RUN poetry config virtualenvs.create false

# Make site packages location more accessible (for use with volumes)
RUN ln -s $(pyenv prefix)/lib/python3.6/site-packages site-packages

USER root
COPY acapy_plugin_pickup acapy-plugin-pickup/acapy_plugin_pickup
COPY README.md acapy-plugin-pickup
COPY setup.py acapy-plugin-pickup
COPY pyproject.toml acapy-plugin-pickup
COPY poetry.lock acapy-plugin-pickup
COPY docker/default.yml .
RUN chown -R indy:indy acapy-plugin-pickup
USER $user

RUN cd acapy-plugin-pickup; poetry install --no-dev
RUN pip3 install -I --no-cache git+https://github.com/dbluhm/aries-cloudagent-python.git@feature/transport-manager-access

ENTRYPOINT ["/bin/bash", "-c", "aca-py \"$@\"", "--"]
CMD ["start", "--arg-file", "default.yml"]
