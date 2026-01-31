# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps for common Odoo Python packages (lxml, Pillow, ldap, psycopg2, etc.)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    gcc \
    g++ \
    make \
    pkg-config \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    libffi-dev \
    zlib1g-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libwebp-dev \
    postgresql-client \
    wkhtmltopdf \
 && rm -rf /var/lib/apt/lists/*

# Create user and dirs
RUN useradd -m -U -r -d /var/lib/odoo -s /bin/bash odoo \
 && mkdir -p /opt/odoo /etc/odoo /var/lib/odoo \
 && chown -R odoo:odoo /opt/odoo /etc/odoo /var/lib/odoo

WORKDIR /opt/odoo

# Install python deps first (better layer caching)
COPY requirements.txt /opt/odoo/requirements.txt
RUN pip install --upgrade pip wheel setuptools \
 && pip install -r /opt/odoo/requirements.txt

# Copy Odoo sources
COPY --chown=odoo:odoo odoo /opt/odoo/odoo
COPY --chown=odoo:odoo odoo-bin /opt/odoo/odoo-bin
COPY --chown=odoo:odoo setup.py setup.cfg MANIFEST.in PKG-INFO /opt/odoo/

# Runtime config + entrypoint
COPY docker/odoo.conf /etc/odoo/odoo.conf
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /opt/odoo/odoo-bin \
 && chown odoo:odoo /entrypoint.sh

USER odoo

EXPOSE 8069

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/opt/odoo/odoo-bin", "-c", "/etc/odoo/odoo.conf"]
