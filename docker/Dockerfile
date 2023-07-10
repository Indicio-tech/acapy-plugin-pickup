FROM python:3.9-slim-bullseye AS base
WORKDIR /usr/src/app

# Install and configure poetry
RUN apt-get update && apt-get install -y curl && apt-get clean
ENV POETRY_VERSION=1.4.2
ENV POETRY_HOME=/opt/poetry
RUN curl -sSL https://install.python-poetry.org | python -

ENV PATH="/opt/poetry/bin:$PATH"
RUN poetry config virtualenvs.in-project true

# Setup project
RUN mkdir acapy_plugin_pickup && touch acapy_plugin_pickup/__init__.py
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --without=dev

FROM python:3.9-slim-bullseye AS final
WORKDIR /usr/src/app
COPY --from=base /usr/src/app/.venv /usr/src/app/.venv
ENV PATH="/usr/src/app/.venv/bin:$PATH"
EXPOSE 80

COPY docker/default.yml .
COPY acapy_plugin_pickup/ acapy_plugin_pickup/

ENTRYPOINT ["/bin/bash", "-c", "aca-py \"$@\"", "--"]
CMD ["start", "--arg-file", "default.yml"]
