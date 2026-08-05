include config.mk

HTTP_AVAIL    = services/nginx/etc/nginx/conf.d/http.available
HTTP_SVC      = services/nginx/etc/nginx/conf.d/http/services
STREAM_AVAIL  = services/nginx/etc/nginx/conf.d/stream.available
STREAM_SVC    = services/nginx/etc/nginx/conf.d/stream/services
FRONTEND_DIR  = services/dashboard/frontend
NODE_IMAGE    = node:22-alpine

PROFILES        =
HTTP_SERVICES   =
STREAM_SERVICES =

ifeq ($(ENABLE_OPENSEARCH),true)
  PROFILES        += --profile opensearch
  HTTP_SERVICES   += opensearch
endif
ifeq ($(ENABLE_LOCALSTACK),true)
  PROFILES        += --profile localstack
endif
ifeq ($(ENABLE_ACTIVEMQ),true)
  PROFILES        += --profile activemq
  HTTP_SERVICES   += activemq
  STREAM_SERVICES += activemq
endif
ifeq ($(ENABLE_KAFKA),true)
  PROFILES        += --profile kafka
  HTTP_SERVICES   += kafka
  STREAM_SERVICES += kafka
endif
ifeq ($(ENABLE_POSTGRES),true)
  PROFILES        += --profile postgres
  HTTP_SERVICES   += postgres
endif

.PHONY: help up down restart status logs nginx-sync nginx-reload dashboard-build dashboard-build-force

help:
	@echo "Uso: make [objetivo]"
	@echo ""
	@echo "Objetivos:"
	@echo "  up                    Compila el dashboard (si hace falta), sincroniza nginx y arranca los servicios habilitados en config.mk"
	@echo "  down                  Para todos los servicios"
	@echo "  restart               down + up"
	@echo "  status                Estado de los contenedores"
	@echo "  logs                  Logs en tiempo real de los servicios activos"
	@echo "  nginx-reload          Recarga la config de nginx sin reiniciar el contenedor"
	@echo "  nginx-sync            Sincroniza los .conf de nginx segun config.mk (lo hace up automaticamente)"
	@echo "  dashboard-build       Compila el frontend del dashboard solo si no existe ya (lo hace up automaticamente)"
	@echo "  dashboard-build-force Recompila el frontend del dashboard aunque ya exista (tras cambios en services/dashboard/frontend/src)"
	@echo ""
	@echo "Servicios opcionales (editar config.mk):"
	@echo "  ENABLE_OPENSEARCH=$(ENABLE_OPENSEARCH)"
	@echo "  ENABLE_LOCALSTACK=$(ENABLE_LOCALSTACK)"
	@echo "  ENABLE_ACTIVEMQ=$(ENABLE_ACTIVEMQ)"
	@echo "  ENABLE_KAFKA=$(ENABLE_KAFKA)"
	@echo "  ENABLE_POSTGRES=$(ENABLE_POSTGRES)"

up: nginx-sync dashboard-build
	docker compose $(PROFILES) up -d

down:
	docker compose \
	  --profile opensearch \
	  --profile localstack \
	  --profile activemq \
	  --profile kafka \
	  --profile postgres \
	  down

restart: down up

nginx-sync:
	@mkdir -p $(HTTP_SVC) $(STREAM_SVC)
	@rm -f $(HTTP_SVC)/*.conf $(STREAM_SVC)/*.conf
	@$(foreach s,$(HTTP_SERVICES),cp $(HTTP_AVAIL)/$(s).conf $(HTTP_SVC)/$(s).conf ; echo "  [nginx] activando $(s) (http)";)
	@$(foreach s,$(STREAM_SERVICES),cp $(STREAM_AVAIL)/$(s).conf $(STREAM_SVC)/$(s).conf ; echo "  [nginx] activando $(s) (stream)";)
	@echo "nginx sync completo: http=[$(HTTP_SERVICES)] stream=[$(STREAM_SERVICES)]"

nginx-reload:
	docker compose exec nginx nginx -s reload

dashboard-build:
	@if [ ! -f $(FRONTEND_DIR)/dist/index.html ]; then \
	  $(MAKE) dashboard-build-force; \
	else \
	  echo "  [dashboard] frontend ya compilado, se omite (usa 'make dashboard-build-force' para recompilar)"; \
	fi

dashboard-build-force:
	@echo "  [dashboard] compilando frontend..."
	@docker run --rm \
	  --user $$(id -u):$$(id -g) \
	  -v $(CURDIR)/$(FRONTEND_DIR):/app \
	  -w /app \
	  $(NODE_IMAGE) \
	  sh -c "npm install && npm run build"

status:
	@docker compose ps

logs:
	@docker compose $(PROFILES) logs -f
