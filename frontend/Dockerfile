# ============================================
# Dockerfile for Angular Frontend
# ============================================

# Stage 1: Build Angular application
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy source code
COPY . .

# Build Angular app for production
RUN npm run build

# ============================================
# Stage 2: Serve with Nginx
# ============================================
FROM nginx:alpine

# Remove default nginx website
RUN rm -rf /usr/share/nginx/html/*
RUN rm /etc/nginx/nginx.conf


# Copy built application
COPY --from=builder /app/dist/construction-inventory-frontend /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create the temp directories defined in nginx.conf
RUN mkdir -p /tmp/client_temp \
             /tmp/proxy_temp_path \
             /tmp/fastcgi_temp \
             /tmp/uwsgi_temp \
             /tmp/scgi_temp

#Give ownership to the default 'nginx' user

RUN chown -R nginx:nginx /usr/share/nginx/html \
    /etc/nginx/nginx.conf \
    /var/log/nginx \          
    /var/cache/nginx \        
    /tmp/client_temp \
    /tmp/proxy_temp_path \
    /tmp/fastcgi_temp \
    /tmp/uwsgi_temp \
    /tmp/scgi_temp

# Copy custom mime types if exists
COPY mime.types* /etc/nginx/mime.types 

# Create the user and group (Alpine syntax)
#RUN addgroup -g 1000 -S appgroup && \
#    adduser -S -D -H -u 1000 -h /var/cache/nginx -s /sbin/nologin -G appgroup appuser

# 1. Ownership of web files (so you can overwrite them if needed)
#RUN chown -R appuser:appgroup /usr/share/nginx/html && \
#    chmod -R 755 /usr/share/nginx/html

# 3. Handle the PID file (Using /tmp is safer for non-root)
#    Ensure your nginx.conf has: pid /tmp/nginx.pid;
RUN touch /tmp/nginx.pid && \
    chown nginx:nginx /tmp/nginx.pid


# 2. Ownership of Nginx internal folders (CRITICAL for the permission error)
RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx /etc/nginx/conf.d

# 3. Handle the PID file (CRITICAL)
# Nginx tries to write this as root by default. We create it empty and give it to appuser.
RUN touch /var/run/nginx.pid && \
    chown nginx:nginx /var/run/nginx.pid

# Switch to non-root
USER nginx

# Switch to non-root user

# Expose pot
EXPOSE 8080

# Health check
#HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
 #   CMD curl -f http://localhost/ || exit 1

HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget -q --spider http://localhost || exit 1

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
