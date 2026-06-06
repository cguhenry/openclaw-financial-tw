FROM node:20-alpine AS build

WORKDIR /app
COPY dashboard/web/package.json ./package.json
COPY dashboard/web/tsconfig.json ./tsconfig.json
COPY dashboard/web/tsconfig.node.json ./tsconfig.node.json
COPY dashboard/web/vite.config.ts ./vite.config.ts
COPY dashboard/web/index.html ./index.html
COPY dashboard/web/src ./src
RUN npm install && npm run build

FROM nginx:1.27-alpine
COPY dashboard/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
