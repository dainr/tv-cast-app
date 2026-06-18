const express = require('express');
const cors = require('cors');
const fetch = require('node-fetch');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Simple in-memory state
let currentMedia = {
  url: '',
  timestamp: Date.now(),
  title: 'No media playing'
};

// Log requests
app.use((req, res, next) => {
  console.log(`${req.method} ${req.url}`);
  next();
});

// TV polling endpoint (highly compatible with older TV browsers)
app.get('/api/state', (req, res) => {
  res.json(currentMedia);
});

// Client endpoint to play a link
app.post('/api/play', (req, res) => {
  const { url, title } = req.body;
  if (!url) {
    return res.status(400).json({ error: 'URL is required' });
  }

  currentMedia = {
    url: url,
    timestamp: Date.now(),
    title: title || 'Cast Media'
  };

  console.log(`Now playing: ${url}`);
  res.json({ success: true, state: currentMedia });
});

// A media proxy to bypass CORS / Mixed Content issues in TV browsers.
// Pipes the video stream directly through the server if needed.
app.get('/api/proxy', async (req, res) => {
  const targetUrl = req.query.url;
  if (!targetUrl) {
    return res.status(400).send('Missing url parameter');
  }

  try {
    console.log(`Proxying request to: ${targetUrl}`);
    
    // Set up headers to mimic a normal browser request to bypass basic hotlinking/CORS protection
    const headers = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Referer': new URL(targetUrl).origin,
      'Accept': '*/*'
    };

    // Forward Range header if present (important for video seeking)
    if (req.headers.range) {
      headers['Range'] = req.headers.range;
    }

    const response = await fetch(targetUrl, { headers });

    // Copy essential headers back to the client
    const contentRange = response.headers.get('content-range');
    const contentType = response.headers.get('content-type');
    const contentLength = response.headers.get('content-length');
    const acceptRanges = response.headers.get('accept-ranges');

    res.status(response.status);

    if (contentRange) res.setHeader('Content-Range', contentRange);
    if (contentType) res.setHeader('Content-Type', contentType);
    if (contentLength) res.setHeader('Content-Length', contentLength);
    if (acceptRanges) res.setHeader('Accept-Ranges', acceptRanges);
    
    // Standard streaming header configuration
    res.setHeader('Access-Control-Allow-Origin', '*');

    // Pipe the response body stream to the client
    response.body.pipe(res);
  } catch (error) {
    console.error('Proxy error:', error.message);
    res.status(500).send(`Error proxying stream: ${error.message}`);
  }
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`TV Cast server running on port ${PORT}`);
});
