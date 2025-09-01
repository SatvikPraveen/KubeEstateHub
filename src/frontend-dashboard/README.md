# Location: `/src/frontend-dashboard/README.md`

# Frontend Dashboard

Modern, responsive web dashboard for the KubeEstateHub real estate management platform.

## Features

- **Responsive Design** - Works on desktop, tablet, and mobile devices
- **Dark/Light Theme** - Toggle between light and dark modes
- **Real-time Data** - Live connection to listings API
- **Interactive Charts** - Market trends and analytics visualization
- **Property Management** - View, filter, and add property listings
- **Progressive Web App** - PWA-ready with service worker
- **Accessibility** - WCAG compliant interface design

## Technology Stack

- **HTML5** - Semantic markup
- **CSS3** - Custom properties, Grid, Flexbox
- **Vanilla JavaScript** - No frameworks, modern ES6+
- **Chart.js** - Data visualization
- **Font Awesome** - Icon library
- **Nginx** - Web server (containerized)

## Project Structure

```
src/frontend-dashboard/
├── index.html          # Main HTML file
├── app.js             # Application logic
├── styles.css         # CSS styles
├── Dockerfile         # Container build
├── nginx.conf         # Nginx configuration
└── README.md          # This file
```

## API Integration

The dashboard connects to the Listings API at:

- Development: `http://localhost:8080/api/v1`
- Production: `/api/v1` (proxied through ingress)

### API Endpoints Used

- `GET /health` - API health check
- `GET /api/v1/listings` - Property listings with pagination/filtering
- `GET /api/v1/listings/{id}` - Individual property details
- `POST /api/v1/listings` - Create new listing

## Features Overview

### Dashboard

- Key metrics display (total listings, average price, market trends)
- Price trend charts
- Property type distribution
- Market performance indicators

### Listings Management

- Paginated property listings
- Advanced filtering (city, type, price range)
- Property cards with images and details
- Add new listing modal form

### Analytics

- Market performance metrics
- Top performing cities
- Interactive trend charts
- Growth indicators

### Settings

- Theme toggle (light/dark mode)
- Display preferences
- API connection status
- Items per page configuration

## Development

### Local Development

```bash
# Serve files with any web server
python -m http.server 3000
# or
npx serve .
# or
php -S localhost:3000
```

### With API Backend

```bash
# Start the listings API first
cd ../listings-api
python app.py

# Then serve frontend
cd ../frontend-dashboard
python -m http.server 3000
```

### Docker Development

```bash
# Build image
docker build -t kubeestatehub/frontend-dashboard .

# Run container
docker run -p 3000:80 kubeestatehub/frontend-dashboard
```

## Configuration

### Environment Detection

The app automatically detects the environment:

- **Local**: Uses `http://localhost:8080/api/v1`
- **Production**: Uses `/api/v1` (reverse proxied)

### Theme Persistence

- User theme preference saved in localStorage
- Automatic dark/light mode toggle
- System preference detection

### Settings Storage

- Items per page: localStorage
- Theme preference: localStorage
- Filter state: sessionStorage

## Responsive Design

### Breakpoints

- **Desktop**: > 768px (full layout)
- **Tablet**: 768px (adapted grid)
- **Mobile**: < 768px (single column)

### Mobile Optimizations

- Touch-friendly buttons (min 44px)
- Simplified navigation
- Collapsible filters
- Stack charts vertically
- Full-width cards

## Performance Features

- **Lazy Loading** - Charts initialized when sections are viewed
- **Image Optimization** - Responsive images with fallbacks
- **Caching** - API responses cached in browser
- **Compression** - Gzip enabled in nginx
- **CDN Assets** - Icons and fonts from CDN

## Security Features

- **CSP Headers** - Content Security Policy enabled
- **XSS Protection** - Input sanitization
- **HTTPS Ready** - Secure headers configured
- **CORS Handling** - Proper cross-origin setup

## Browser Support

- **Chrome/Edge**: 90+
- **Firefox**: 90+
- **Safari**: 14+
- **Mobile**: iOS 14+, Android Chrome 90+

### Modern JavaScript Features Used

- ES6 Modules
- Async/Await
- Fetch API
- Template Literals
- Arrow Functions
- Destructuring

## Customization

### Theming

Modify CSS custom properties in `:root`:

```css
:root {
  --primary-color: #3b82f6;
  --success-color: #22c55e;
  /* ... other properties */
}
```

### API Configuration

Update API base URL in `app.js`:

```javascript
this.apiBaseUrl = "https://your-api-domain.com/api/v1";
```

### Chart Configuration

Customize Chart.js options in the respective init methods:

```javascript
initCharts() {
  // Modify chart configurations
}
```

## Deployment

### Production Build

```bash
# Build optimized container
docker build -t kubeestatehub/frontend-dashboard:v1.0.0 .

# Push to registry
docker push kubeestatehub/frontend-dashboard:v1.0.0
```

### Kubernetes Deployment

The frontend is deployed as part of the KubeEstateHub Helm chart:

```bash
helm install kubeestatehub ./helm-charts/kubeestatehub
```

## Monitoring

### Health Checks

- **Liveness**: HTTP 200 on `/`
- **Readiness**: Static file serving capability
- **Startup**: Nginx process initialization

### Error Handling

- API connection failures shown via toast notifications
- Graceful degradation when API is unavailable
- Loading states for all async operations
- Retry logic for failed requests
