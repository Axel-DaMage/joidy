const fs = require('fs');
const file = '/home/d4mag3/Documents/Repos/Joidy/frontend/src/routes/goals/+page.svelte';
let code = fs.readFileSync(file, 'utf8');

// 1. Imports
code = code.replace(
  /import \{ Plus, .* \} from 'lucide-svelte';/,
  "import { Plus, Check, ChevronDown, Calendar, BarChart, Clock, Layout, Pause, Play, Ban, Pencil, X, Flame, ChevronRight, TrendingUp, TrendingDown, PieChart, Activity, Target, Trophy, Settings, Palette, Hexagon, Filter, AlertTriangle } from 'lucide-svelte';"
);

// 2. Derived variables
const varsInsert = `
  let activityByHour = $derived.by(() => {
    const counts = new Array(24).fill(0);
    goals.forEach(g => {
      if ((g.state === 'COMPLETED' || g.is_completed) && g.completed_at) {
        const hour = new Date(g.completed_at).getHours();
        if(!isNaN(hour)) counts[hour]++;
      }
    });
    const maxVal = Math.max(...counts) || 1;
    return counts.map((c, i) => ({
      hour: i,
      label: \`\${i.toString().padStart(2, '0')}:00\`,
      val: c,
      pct: c / maxVal
    }));
  });

  let radarData = $derived.by(() => {
    const categories = topTagsBySuccess.slice(0, 6);
    while(categories.length > 0 && categories.length < 3) {
      categories.push({name: '', count: 0});
    }
    if(categories.length === 0) return [];
    const maxVal = Math.max(...categories.map(c => c.count)) || 1;
    return categories.map((c, i) => {
      const angle = (Math.PI * 2 * i) / categories.length - Math.PI / 2;
      return {
        name: c.name,
        value: c.count,
        pct: c.count / maxVal,
        x: 50 + 40 * Math.cos(angle),
        y: 50 + 40 * Math.sin(angle),
        labelX: 50 + 50 * Math.cos(angle),
        labelY: 50 + 50 * Math.sin(angle)
      };
    });
  });

  let debtData = $derived.by(() => {
    const dGoals = goals.filter(g => (g.fail_config === 'ROLLOVER' || g.fail_config === 'SNOWBALL') && g.state === 'ACTIVE');
    const total = dGoals.reduce((acc, g) => acc + Math.max(0, g.target_value - g.current_value), 0);
    return {
      goals: dGoals.map(g => ({ title: g.title, debt: Math.max(0, g.target_value - g.current_value) })).sort((a,b)=>b.debt-a.debt).slice(0, 5),
      total
    };
  });

  let funnelData = $derived.by(() => {
    const total = goals.length || 1;
    const completed = goals.filter(g => g.state === 'COMPLETED' || g.is_completed).length;
    const failed = goals.filter(g => g.state === 'FAILED').length;
    const active = goals.filter(g => g.state === 'ACTIVE').length;
    const cancelled = goals.filter(g => g.state === 'CANCELLED' || g.state === 'PAUSED').length;
    return [
      { label: 'Iniciados', value: total, color: 'var(--text-disabled)' },
      { label: 'Activos', value: active, color: 'var(--xp)' },
      { label: 'Completados', value: completed, color: 'var(--success)' },
      { label: 'Abandonados', value: cancelled + failed, color: 'var(--error)' }
    ];
  });
`;
code = code.replace(/  let candleScale = \$derived\.by\(\(\) => \{[\s\S]*?\}\);\n/, match => match + varsInsert);

// 3. HTML replacement (replace tags-card and summary-card)
const oldHtmlStart = `          <div class="dash-card tags-card">`;
const oldHtmlEnd = `              </div>
            </div>
          </div>

        </div>`;
const newHtml = `          <div class="dash-card hourly-card">
            <div class="dash-card-header">
              <Clock size={16} />
              <span>Actividad Horaria</span>
            </div>
            <div class="hourly-chart">
              {#each activityByHour as hour}
                <div class="hour-col" title="{hour.label}: {hour.val} completados">
                  <div class="hour-bar-wrap">
                    <div class="hour-bar" style="height: {hour.pct * 100}%; opacity: {Math.max(0.15, hour.pct)};"></div>
                  </div>
                  {#if hour.hour % 4 === 0}
                    <span class="hour-label">{hour.hour}h</span>
                  {/if}
                </div>
              {/each}
            </div>
          </div>

          <div class="dash-card radar-card">
            <div class="dash-card-header">
              <Hexagon size={16} />
              <span>Radar de Foco</span>
            </div>
            <div class="radar-container">
              {#if radarData.length === 0}
                <div class="empty-state mini">Sin datos suficientes</div>
              {:else}
                <svg viewBox="0 0 100 100" class="radar-svg">
                  {#each [20, 40, 60, 80, 100] as r}
                    <polygon points={radarData.map(d => \`\${50 + (r/100)*40*Math.cos(d.angle)},\${50 + (r/100)*40*Math.sin(d.angle)}\`).join(' ')} fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="0.5" />
                  {/each}
                  {#each radarData as d}
                    <line x1="50" y1="50" x2={50 + 40*Math.cos(d.angle)} y2={50 + 40*Math.sin(d.angle)} stroke="rgba(255,255,255,0.05)" stroke-width="0.5" />
                    <text x={d.labelX} y={d.labelY} font-size="4" fill="var(--text-muted)" text-anchor="middle" dominant-baseline="middle" font-family="var(--font-mono)">
                      {d.name.substring(0,8)}
                    </text>
                  {/each}
                  <polygon points={radarData.map(d => \`\${50 + d.pct*40*Math.cos(d.angle)},\${50 + d.pct*40*Math.sin(d.angle)}\`).join(' ')} fill="var(--xp)" fill-opacity="0.3" stroke="var(--xp)" stroke-width="1" stroke-linejoin="round" />
                  {#each radarData as d}
                    <circle cx={50 + d.pct*40*Math.cos(d.angle)} cy={50 + d.pct*40*Math.sin(d.angle)} r="1.5" fill="var(--surface)" stroke="var(--xp)" stroke-width="1" />
                  {/each}
                </svg>
              {/if}
            </div>
          </div>

          <div class="dash-card debt-card">
            <div class="dash-card-header">
              <Flame size={16} class="text-error" />
              <span>Deuda Acumulada</span>
            </div>
            <div class="debt-content">
              <div class="debt-total">
                <span class="debt-val">{debtData.total}</span>
                <span class="debt-lab">Pendientes</span>
              </div>
              <div class="debt-list">
                {#if debtData.goals.length === 0}
                   <div class="empty-state mini">Cero deudas. ¡Excelente!</div>
                {:else}
                  {#each debtData.goals as d}
                    <div class="debt-item">
                      <span class="debt-title">{d.title}</span>
                      <div class="debt-bar-wrap">
                        <div class="debt-bar" style="width: {(d.debt / (debtData.goals[0]?.debt || 1)) * 100}%"></div>
                      </div>
                      <span class="debt-count">{d.debt}</span>
                    </div>
                  {/each}
                {/if}
              </div>
            </div>
          </div>

          <div class="dash-card funnel-card">
            <div class="dash-card-header">
              <Filter size={16} />
              <span>Conversión y Abandono</span>
            </div>
            <div class="funnel-chart">
              {#each funnelData as f}
                <div class="funnel-row">
                  <div class="funnel-label-col">
                    <span class="funnel-name">{f.label}</span>
                    <span class="funnel-val" style="color: {f.color}">{f.value}</span>
                  </div>
                  <div class="funnel-bar-col">
                    <div class="funnel-bar" style="width: {(f.value / (funnelData[0]?.value || 1)) * 100}%; background: {f.color};"></div>
                  </div>
                </div>
              {/each}
            </div>
          </div>

        </div>`;
const startIndex = code.indexOf(oldHtmlStart);
const endIndex = code.indexOf(oldHtmlEnd, startIndex) + oldHtmlEnd.length;
if(startIndex !== -1 && endIndex !== -1) {
  code = code.substring(0, startIndex) + newHtml + code.substring(endIndex);
}

// 4. CSS for dashboard-grid
code = code.replace(
  /\.full-height-dashboard \{\s*height: calc\(100vh - 150px\);\s*overflow: hidden;/,
  `.full-height-dashboard {
    height: calc(100vh - 150px);
    overflow-y: auto;`
);

code = code.replace(
  /\.dashboard-grid \{\s*display: grid;\s*grid-template-columns: repeat\(3, 1fr\);\s*grid-template-rows: repeat\(2, 1fr\);\s*gap: var\(--s3\);\s*flex: 1;\s*min-height: 0;\s*\}/,
  `.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    grid-auto-rows: minmax(180px, auto);
    gap: var(--s3);
    flex: 1;
  }`
);

// 5. CSS for new components
const cssInsert = `
  /* Advanced Analytics Styles */
  .dash-card { grid-column: span 2; }
  .radar-card { grid-column: span 1; }
  .funnel-card { grid-column: span 1; }
  
  .hourly-chart {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    height: 100%;
    padding-top: var(--s2);
  }
  .hour-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    flex: 1;
  }
  .hour-bar-wrap {
    flex: 1;
    width: 10px;
    background: rgba(255,255,255,0.02);
    border-radius: 5px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
  }
  .hour-bar {
    width: 100%;
    background: linear-gradient(0deg, transparent, var(--xp));
    border-radius: 5px;
    transition: height 0.5s;
  }
  .hour-label {
    font-size: 8px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .radar-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--s2);
  }
  .radar-svg {
    width: 100%;
    height: 100%;
    max-height: 180px;
    overflow: visible;
  }

  .debt-content {
    display: flex;
    gap: var(--s4);
    height: 100%;
    align-items: center;
  }
  .debt-total {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 50%;
    width: 80px;
    height: 80px;
    flex-shrink: 0;
  }
  .debt-val {
    font-size: 24px;
    font-weight: 700;
    color: var(--error);
    font-family: var(--font-mono);
    line-height: 1;
  }
  .debt-lab {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
  }
  .debt-list {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .debt-item {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .debt-title {
    font-size: 11px;
    color: var(--text-primary);
    width: 80px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .debt-bar-wrap {
    flex: 1;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
  }
  .debt-bar {
    height: 100%;
    background: var(--error);
    border-radius: 3px;
  }
  .debt-count {
    font-size: 11px;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--error);
  }

  .funnel-chart {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    height: 100%;
    justify-content: center;
  }
  .funnel-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .funnel-label-col {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
  }
  .funnel-name {
    color: var(--text-muted);
    text-transform: uppercase;
    font-size: 9px;
    letter-spacing: 0.05em;
  }
  .funnel-val {
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .funnel-bar-col {
    height: 8px;
    background: var(--border);
    border-radius: 4px;
  }
  .funnel-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s;
  }
`;

code = code.replace(/<\/style>/, cssInsert + '\n</style>');

fs.writeFileSync(file, code);
