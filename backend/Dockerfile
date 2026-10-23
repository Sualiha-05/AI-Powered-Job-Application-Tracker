# Stage "build": full dependencies. docker-compose targets this stage for local dev
# (it overrides the command with `npm run start:dev`).
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Final stage (the default, used by Render): production dependencies + compiled code only.
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY package*.json ./
RUN npm ci --omit=dev
COPY --from=build /app/dist ./dist
EXPOSE 3001
CMD ["node", "dist/main"]
