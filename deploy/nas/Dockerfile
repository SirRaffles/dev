#
# Whisper Transcription Frontend
# Multi-stage build for minimal image size
#

# Stage 1: Build React app
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY public ./public
COPY src ./src
COPY index.html ./
COPY vite.config.js ./
COPY tailwind.config.cjs ./
COPY postcss.config.cjs ./

# Build argument for backend URL (empty = same-origin)
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL

# Build the app
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

# Copy custom nginx config
COPY deploy/nas/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built app
COPY --from=builder /app/build /usr/share/nginx/html

# Add healthcheck
RUN apk add --no-cache curl

# Expose ports
EXPOSE 80 443

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
