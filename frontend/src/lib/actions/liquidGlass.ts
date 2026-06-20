type LiquidGlassOptions = {
  enabled: boolean;
  blur?: number;
  chromaticAberration?: number;
  depth?: number;
  strength?: number;
  saturate?: number;
  brightness?: number;
};

export function liquidGlass(node: HTMLElement, options: LiquidGlassOptions) {
  let ro: ResizeObserver | null = null;
  let isEnabled = options.enabled;

  let bgLayer: HTMLDivElement | null = null;
  let glassLayer: HTMLDivElement | null = null;
  let reflectionLayer: HTMLDivElement | null = null;

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
    if (bgLayer && glassLayer) return;
    ensureAuroraFilter();
    ensureKeyframes();

    bgLayer = document.createElement('div');
    bgLayer.className = 'lg-bg-layer';
    Object.assign(bgLayer.style, {
      position: 'absolute',
      inset: '-20%',
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

    glassLayer = document.createElement('div');
    glassLayer.className = 'lg-glass-layer';
    Object.assign(glassLayer.style, {
      position: 'absolute',
      inset: '0',
      zIndex: '0',
      pointerEvents: 'none',
      borderRadius: 'inherit',
      background: 'rgba(255, 255, 255, 0.15)',
      boxShadow: '0 8px 32px rgba(31, 38, 135, 0.2), inset 0 4px 20px rgba(255, 255, 255, 0.3)',
      backdropFilter: 'blur(16px) saturate(180%)',
      WebkitBackdropFilter: 'blur(16px) saturate(180%)'
    });

    reflectionLayer = document.createElement('div');
    reflectionLayer.className = 'lg-reflection-layer';
    Object.assign(reflectionLayer.style, {
      position: 'absolute',
      inset: '0',
      zIndex: '2', // Above content for reflections
      pointerEvents: 'none',
      borderRadius: 'inherit',
      background: 'rgba(255, 255, 255, 0.1)',
      backdropFilter: 'blur(1px)',
      WebkitBackdropFilter: 'blur(1px)',
      boxShadow: 'inset -10px -8px 0px -11px rgba(255, 255, 255, 1), inset 0px -9px 0px -8px rgba(255, 255, 255, 1)',
      opacity: '0.6',
      filter: 'blur(1px) drop-shadow(10px 4px 6px rgba(0,0,0,0.5)) brightness(115%)'
    });

    node.appendChild(bgLayer);
    node.appendChild(glassLayer);
    node.appendChild(reflectionLayer);
    
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
    if (glassLayer && glassLayer.parentNode) glassLayer.parentNode.removeChild(glassLayer);
    if (reflectionLayer && reflectionLayer.parentNode) reflectionLayer.parentNode.removeChild(reflectionLayer);
    bgLayer = null;
    glassLayer = null;
    reflectionLayer = null;
  }

  function applyFilter() {
    if (!isEnabled) {
      unmountLayers();
      return;
    }
    mountLayers();
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
