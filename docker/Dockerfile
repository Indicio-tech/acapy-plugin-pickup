FROM bcgovimages/von-image:py36-1.16-1

USER root
ENV POETRY_HOME=/opt/poetry \
    VENV=/usr/src/app/.venv
ENV PATH="$POETRY_HOME/bin:$VENV/bin:$PATH"

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -
RUN poetry config virtualenvs.create true; poetry config virtualenvs.in-project true

RUN mkdir acapy_plugin_pickup && touch acapy_plugin_pickup/__init__.py
COPY README.md setup.py pyproject.toml poetry.lock .

RUN poetry install --no-dev
USER $user

# Make site packages location more accessible (for use with volumes)
RUN ln -s $(poetry env info -p)/lib/python3.6/site-packages site-packages

COPY docker/default.yml .
COPY acapy_plugin_pickup/ acapy_plugin_pickup/

ENTRYPOINT ["/bin/bash", "-c", "poetry run aca-py \"$@\"", "--"]
CMD ["start", "--arg-file", "default.yml"]
