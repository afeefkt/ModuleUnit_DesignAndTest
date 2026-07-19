FROM nginx:alpine

# Copy static files
COPY index.html /usr/share/nginx/html/
COPY analyze.html /usr/share/nginx/html/
COPY generate.html /usr/share/nginx/html/
COPY history.html /usr/share/nginx/html/
COPY css/ /usr/share/nginx/html/css/
COPY js/ /usr/share/nginx/html/js/

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
