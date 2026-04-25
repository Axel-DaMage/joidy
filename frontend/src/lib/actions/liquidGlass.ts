type LiquidGlassOptions = {
  enabled: boolean;
  blur?: number;
  chromaticAberration?: number;
  depth?: number;
  strength?: number;
  saturate?: number;
  brightness?: number;
};

const getDisplacementMap = ({
  height,
  width,
  radius,
  depth,
}: { height: number; width: number; radius: number; depth: number; }) =>
  "data:image/svg+xml;utf8," +
  encodeURIComponent(`<svg height="${height}" width="${width}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
    <style>
        .mix { mix-blend-mode: screen; }
    </style>
    <defs>
        <linearGradient 
          id="Y" 
          x1="0" 
          x2="0" 
          y1="${Math.ceil((radius / height) * 15)}%" 
          y2="${Math.floor(100 - (radius / height) * 15)}%">
            <stop offset="0%" stop-color="#0F0" />
            <stop offset="100%" stop-color="#000" />
        </linearGradient>
        <linearGradient 
          id="X" 
          x1="${Math.ceil((radius / width) * 15)}%" 
          x2="${Math.floor(100 - (radius / width) * 15)}%"
          y1="0" 
          y2="0">
            <stop offset="0%" stop-color="#F00" />
            <stop offset="100%" stop-color="#000" />
        </linearGradient>
    </defs>

    <rect x="0" y="0" height="${height}" width="${width}" fill="#808080" />
    <g filter="blur(2px)">
      <rect x="0" y="0" height="${height}" width="${width}" fill="#000080" />
      <rect
          x="0"
          y="0"
          height="${height}"
          width="${width}"
          fill="url(#Y)"
          class="mix"
      />
      <rect
          x="0"
          y="0"
          height="${height}"
          width="${width}"
          fill="url(#X)"
          class="mix"
      />
      <rect
          x="${depth}"
          y="${depth}"
          height="${height - 2 * depth}"
          width="${width - 2 * depth}"
          fill="#808080"
          rx="${radius}"
          ry="${radius}"
          filter="blur(${depth}px)"
      />
    </g>
</svg>`);

const getDisplacementFilter = ({
  height,
  width,
  radius,
  depth,
  strength = 100,
  chromaticAberration = 0,
}: { height: number; width: number; radius: number; depth: number; strength?: number; chromaticAberration?: number; }) =>
  "data:image/svg+xml;utf8," +
  encodeURIComponent(`<svg height="${height}" width="${width}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <filter id="displace" color-interpolation-filters="sRGB">
            <feImage x="0" y="0" height="${height}" width="${width}" href="${getDisplacementMap(
              {
                height,
                width,
                radius,
                depth,
              },
            )}" result="displacementMap" />
            <feDisplacementMap
                transform-origin="center"
                in="SourceGraphic"
                in2="displacementMap"
                scale="${strength + chromaticAberration * 2}"
                xChannelSelector="R"
                yChannelSelector="G"
            />
            <feColorMatrix
            type="matrix"
            values="1 0 0 0 0
                    0 0 0 0 0
                    0 0 0 0 0
                    0 0 0 1 0"
            result="displacedR"
                    />
            <feDisplacementMap
                in="SourceGraphic"
                in2="displacementMap"
                scale="${strength + chromaticAberration}"
                xChannelSelector="R"
                yChannelSelector="G"
            />
            <feColorMatrix
            type="matrix"
            values="0 0 0 0 0
                    0 1 0 0 0
                    0 0 0 0 0
                    0 0 0 1 0"
            result="displacedG"
                    />
            <feDisplacementMap
                    in="SourceGraphic"
                    in2="displacementMap"
                    scale="${strength}"
                    xChannelSelector="R"
                    yChannelSelector="G"
                />
                <feColorMatrix
                type="matrix"
                values="0 0 0 0 0
                        0 0 0 0 0
                        0 0 1 0 0
                        0 0 0 1 0"
                result="displacedB"
                        />
              <feBlend in="displacedR" in2="displacedG" mode="screen"/>
              <feBlend in2="displacedB" mode="screen"/>
        </filter>
    </defs>
</svg>`) +
  "#displace";

const supportsBackdropFilterUrl = typeof window !== 'undefined' ? (() => {
  const testEl = document.createElement("div");
  testEl.style.cssText = "backdrop-filter: url(#test)";
  return (
    testEl.style.backdropFilter === "url(#test)" ||
    testEl.style.backdropFilter === 'url("#test")'
  );
})() : false;

export function liquidGlass(node: HTMLElement, options: LiquidGlassOptions) {
  let ro: ResizeObserver | null = null;
  let isEnabled = options.enabled;

  let bgLayer: HTMLDivElement | null = null;
  let filterLayer: HTMLDivElement | null = null;

  function ensureAuroraFilter() {
    if (!document.getElementById('aurora-svg-filter')) {
      const svg = document.createElement('div');
      svg.innerHTML = `
        <svg style="display:none;" id="aurora-svg-filter">
          <filter id="aurora-turbulence">
            <feTurbulence type="fractalNoise" baseFrequency="0.005 0.01" numOctaves="4" seed="5">
              <animate attributeName="baseFrequency" dur="25s" values="0.005 0.01;0.01 0.02;0.005 0.01" repeatCount="indefinite" />
            </feTurbulence>
            <feDisplacementMap in="SourceGraphic" scale="80" xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </svg>
      `;
      document.body.appendChild(svg);
    }
  }

  function ensureKeyframes() {
    if (!document.getElementById('lg-pan-style')) {
      const style = document.createElement('style');
      style.id = 'lg-pan-style';
      style.textContent = `
        @keyframes lg-pan {
          0% { background-position: 0% 50%; }
          100% { background-position: 100% 50%; }
        }
      `;
      document.head.appendChild(style);
    }
  }

  function mountLayers() {
    if (bgLayer && filterLayer) return;
    ensureAuroraFilter();
    ensureKeyframes();

    bgLayer = document.createElement('div');
    bgLayer.className = 'lg-bg-layer';
    Object.assign(bgLayer.style, {
      position: 'absolute',
      inset: '-20%', // Large inset to hide heavy displacement tearing at the edges
      zIndex: '0',
      pointerEvents: 'none',
      background: `linear-gradient(
        110deg,
        var(--theme-ac) 0%,
        var(--theme-ac) 15%,
        #ff007f 25%,
        #ffea00 35%,
        var(--theme-ac) 50%,
        #00f0ff 65%,
        #7000ff 80%,
        var(--theme-ac) 100%
      )`,
      backgroundSize: '200% 200%',
      animation: 'lg-pan 8s ease-in-out infinite alternate',
      filter: 'url(#aurora-turbulence)',
      opacity: '0.9'
    });

    filterLayer = document.createElement('div');
    filterLayer.className = 'lg-filter-layer';
    Object.assign(filterLayer.style, {
      position: 'absolute',
      inset: '0',
      zIndex: '0',
      pointerEvents: 'none',
      borderRadius: 'inherit',
      background: 'linear-gradient(135deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.05) 100%)',
      boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.8), inset 0 0 0 1px rgba(255,255,255,0.4)'
    });

    node.appendChild(bgLayer);
    node.appendChild(filterLayer);
    
    // Ensure node clips the oversized background
    if (window.getComputedStyle(node).overflow === 'visible') {
      node.style.overflow = 'hidden';
    }
    if (window.getComputedStyle(node).position === 'static') {
      node.style.position = 'relative';
    }
  }

  function unmountLayers() {
    if (bgLayer && bgLayer.parentNode) bgLayer.parentNode.removeChild(bgLayer);
    if (filterLayer && filterLayer.parentNode) filterLayer.parentNode.removeChild(filterLayer);
    bgLayer = null;
    filterLayer = null;
  }

  function applyFilter() {
    if (!isEnabled) {
      unmountLayers();
      return;
    }

    mountLayers();
    if (!filterLayer) return;

    const {
      blur = 0,
      chromaticAberration = 2,
      depth = 10,
      strength = 50,
      saturate = 1.2,
      brightness = 1.1,
    } = options;

    const rect = node.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    const styles = window.getComputedStyle(node);
    const radius = parseFloat(styles.borderRadius) || 0;

    if (supportsBackdropFilterUrl) {
      const url = getDisplacementFilter({
        height,
        width,
        radius,
        depth,
        strength,
        chromaticAberration
      });
      const filterString = `blur(${blur / 2}px) url('${url}') blur(${blur}px) brightness(${brightness}) saturate(${saturate})`;
      filterLayer.style.backdropFilter = filterString;
      (filterLayer.style as any)['-webkit-backdrop-filter'] = filterString;
    } else {
      // Fallback glass effect
      const fb = `blur(${Math.max(4, width / 20)}px) saturate(180%) brightness(1.1)`;
      filterLayer.style.backdropFilter = fb;
      (filterLayer.style as any)['-webkit-backdrop-filter'] = fb;
    }
  }

  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(() => {
      applyFilter();
    });
    ro.observe(node);
  } else {
    applyFilter();
  }

  return {
    update(newOptions: LiquidGlassOptions) {
      options = newOptions;
      isEnabled = newOptions.enabled;
      applyFilter();
    },
    destroy() {
      if (ro) ro.disconnect();
      unmountLayers();
    }
  };
}
