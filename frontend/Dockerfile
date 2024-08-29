FROM node:20-slim AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /app

FROM base AS prod-deps
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
RUN pnpm add sharp @svgr/webpack  # Install the missing dependencies, needed for efficient building

FROM base
COPY --from=prod-deps /app/node_modules /app/node_modules
COPY . .

CMD [ "sh", "-c", "pnpm run build && pnpm start" ]
