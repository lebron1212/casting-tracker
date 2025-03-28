...
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 10px;
            letter-spacing: 3px;
            font-weight: 400;
            text-transform: uppercase;
            padding: 20px;
            background-color: white;
            color: black;
        }
        h1 { display: none; }
        .block {
            padding: 1rem;
            margin-bottom: 1.5rem;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .block pre {
            white-space: pre-wrap;
            font-family: inherit;
            display: inline-block;
        }
        .cypher {
            display: inline-block;
            overflow: hidden;
            animation: scramble 1.5s steps(20) forwards;
        }
        @keyframes scramble {
            0% { opacity: 0; }
            100% { opacity: 1; }
        }
    </style>
    <script>
      const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!@#$%^&*()';
      function scrambleText(element, finalText, speed = 8) {
        let i = 0;
        function next() {
          if (i >= finalText.length) return;
          let cycles = 0, max = 5;
          const interval = setInterval(() => {
            const scrambled = finalText.substring(0, i) + (finalText[i] === ' ' ? ' ' : chars[Math.floor(Math.random() * chars.length)]) + ' '.repeat(finalText.length - i - 1);
            element.textContent = scrambled;
            if (++cycles >= max) {
              clearInterval(interval);
              element.textContent = finalText.substring(0, ++i);
              next();
            }
          }, speed);
        }
        next();
      }
      window.onload = () => {
        document.querySelectorAll('.block pre').forEach(pre => {
          const text = pre.textContent;
          pre.textContent = '';
          scrambleText(pre, text);
        });
      };
    </script>
</head>
<body>
    <h1>Daily Casting Report – {today}</h1>
