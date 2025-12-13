class STIBWaitTimesCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    if (!config.entities || !Array.isArray(config.entities)) {
      throw new Error('You must define entities as an array');
    }

    this.config = {
      title: config.title || 'STIB Wait Times',
      entities: config.entities,
      line_colors: config.line_colors || {},
      show_header: config.show_header !== false,
      logo_path: config.logo_path || '/local/stib-logo.svg',
      size: config.size || 'normal', // 'compact', 'normal', 'large'
      max_departures: config.max_departures || 2, // 1 or 2 passing times per line
      ...config
    };

    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.updateContent();
  }

  render() {
    const sizeClass = this.config.size || 'normal';
    
    this.shadowRoot.innerHTML = `
      <style>
        ha-card {
          padding: 0;
        }
        .card-header {
          display: flex;
          align-items: center;
          gap: 12px;
          font-size: 24px;
          font-weight: 500;
          padding: 16px;
          border-bottom: 2px solid #e0e0e0;
        }
        ha-card.dark .card-header {
          border-bottom-color: #3a3a3a;
        }
        .stib-logo {
          width: 40px;
          height: 40px;
          flex-shrink: 0;
          object-fit: contain;
        }
        .stib-logo-fallback {
          width: 40px;
          height: 40px;
          flex-shrink: 0;
          background-color: #0066cc;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-weight: bold;
          font-size: 20px;
        }
        .header-title {
          flex: 1;
        }
        .wait-times-container {
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        
        /* Compact size */
        .wait-times-container.compact {
          padding: 8px;
          gap: 4px;
        }
        .wait-times-container.compact .wait-time-row {
          padding: 4px 0;
          gap: 8px;
        }
        .wait-times-container.compact .line-badge {
          min-width: 32px;
          height: 32px;
          font-size: 14px;
          border-radius: 6px;
        }
        .wait-times-container.compact .destination {
          font-size: 13px;
        }
        .wait-times-container.compact .wait-time {
          font-size: 16px;
          min-width: 50px;
        }
        
        /* Normal size (default) */
        .wait-times-container.normal {
          padding: 12px;
          gap: 8px;
        }
        .wait-times-container.normal .wait-time-row {
          padding: 6px 0;
          gap: 10px;
        }
        .wait-times-container.normal .line-badge {
          min-width: 36px;
          height: 36px;
          font-size: 16px;
          border-radius: 7px;
        }
        .wait-times-container.normal .destination {
          font-size: 14px;
        }
        .wait-times-container.normal .wait-time {
          font-size: 18px;
          min-width: 55px;
        }
        
        /* Large size */
        .wait-times-container.large {
          padding: 16px;
          gap: 12px;
        }
        .wait-times-container.large .wait-time-row {
          padding: 8px 0;
          gap: 12px;
        }
        .wait-times-container.large .line-badge {
          min-width: 40px;
          height: 40px;
          font-size: 18px;
          border-radius: 8px;
        }
        .wait-times-container.large .destination {
          font-size: 16px;
        }
        .wait-times-container.large .wait-time {
          font-size: 20px;
          min-width: 60px;
        }
        
        .wait-time-row {
          display: flex;
          align-items: center;
          border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        }
        .wait-time-row:last-child {
          border-bottom: none;
        }
        .line-badge {
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-weight: bold;
          flex-shrink: 0;
        }
        .destination {
          flex: 1;
          font-weight: bold;
        }
        .wait-time {
          font-weight: bold;
          color: var(--primary-color);
          text-align: right;
          flex-shrink: 0;
          display: flex;
          align-items: center;
          justify-content: flex-end;
        }
        .wait-time.soon {
          color: #ff9800;
        }
        .wait-time.now {
          color: #f44336;
        }
        .bus-stop-icon {
          width: 1.2em;
          height: 1.2em;
        }
        .bus-stop-icon svg {
          width: 100%;
          height: 100%;
          fill: currentColor;
        }
        .no-data {
          text-align: center;
          padding: 20px;
          color: var(--secondary-text-color);
          font-style: italic;
        }
      </style>
      <ha-card>
        ${this.config.show_header ? `
          <div class="card-header">
            <img src="${this.config.logo_path}" 
                 class="stib-logo" 
                 alt="STIB Logo"
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
            <div class="stib-logo-fallback" style="display: none;">S</div>
            <div class="header-title">${this.config.title}</div>
          </div>
        ` : ''}
        <div class="wait-times-container ${sizeClass}" id="content">
          <div class="no-data">Loading...</div>
        </div>
      </ha-card>
    `;
  }

  updateContent() {
    if (!this._hass) return;

    const container = this.shadowRoot.getElementById('content');
    if (!container) return;

    // Collect all passing times from all sensors
    const allPassings = [];
    const maxDepartures = this.config.max_departures || 2;

    this.config.entities.forEach(entityId => {
      const state = this._hass.states[entityId];
      if (!state) return;

      const attributes = state.attributes;
      const lineNumber = attributes.line_number;
      const stopName = attributes.stop_name;

      // Get line color from config or use default
      const lineColor = this.config.line_colors[lineNumber] || this.getDefaultColor(attributes.line_type);

      // Add passing times based on max_departures setting
      for (let i = 1; i <= maxDepartures; i++) {
        if (attributes[`next_passing_${i}_destination`]) {
          const minutes = attributes[`next_passing_${i}_minutes`];
          const destination = attributes[`next_passing_${i}_destination`];
          
          // Skip if destination is "Unknown"
          if (destination === "Unknown") {
            continue;
          }
          
          allPassings.push({
            lineNumber,
            lineColor,
            destination,
            minutes: minutes !== undefined ? minutes : null,
            stopName,
            time: attributes[`next_passing_${i}_time`]
          });
        }
      }
    });

    // Sort by minutes (closest first)
    allPassings.sort((a, b) => {
      if (a.minutes === null) return 1;
      if (b.minutes === null) return -1;
      return a.minutes - b.minutes;
    });

    // Render the sorted list
    if (allPassings.length === 0) {
      container.innerHTML = '<div class="no-data">No upcoming departures</div>';
      return;
    }

    container.innerHTML = allPassings.map(passing => {
      let minutesContent;
      let urgencyClass = '';
      
      if (passing.minutes === 0) {
        // Show bus-stop icon for 0 minutes
        minutesContent = `<span class="bus-stop-icon">
          <svg viewBox="0 0 24 24">
            <path d="M12,2C8,2 4.5,3.5 4.5,8V14.5C4.5,16.43 6.07,18 8,18H8.5V20.5A1,1 0 0,0 9.5,21.5A1,1 0 0,0 10.5,20.5V18H13.5V20.5A1,1 0 0,0 14.5,21.5A1,1 0 0,0 15.5,20.5V18H16C17.93,18 19.5,16.43 19.5,14.5V8C19.5,3.5 16,2 12,2M8.5,15A1.5,1.5 0 0,1 7,13.5A1.5,1.5 0 0,1 8.5,12A1.5,1.5 0 0,1 10,13.5A1.5,1.5 0 0,1 8.5,15M12,8.25H6V6H12V8.25M15.5,15A1.5,1.5 0 0,1 14,13.5A1.5,1.5 0 0,1 15.5,12A1.5,1.5 0 0,1 17,13.5A1.5,1.5 0 0,1 15.5,15M18,8.25H12V6H18V8.25Z" />
          </svg>
        </span>`;
        urgencyClass = 'now';
      } else if (passing.minutes !== null) {
        minutesContent = `${passing.minutes} min`;
        urgencyClass = passing.minutes <= 2 ? 'now' : (passing.minutes <= 5 ? 'soon' : '');
      } else {
        minutesContent = 'N/A';
      }

      return `
        <div class="wait-time-row">
          <div class="line-badge" style="background-color: ${passing.lineColor};">
            ${passing.lineNumber}
          </div>
          <div class="destination">
            ${passing.destination}
          </div>
          <div class="wait-time ${urgencyClass}">
            ${minutesContent}
          </div>
        </div>
      `;
    }).join('');
  }

  getDefaultColor(lineType) {
    const defaultColors = {
      'metro': '#0066cc',
      'tram': '#cc0000',
      'bus': '#006633'
    };
    return defaultColors[lineType] || '#666666';
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("stib-wait-times-card-editor");
  }

  static getStubConfig() {
    return {
      title: "STIB Wait Times",
      entities: [],
      line_colors: {}
    };
  }
}

customElements.define('stib-wait-times-card', STIBWaitTimesCard);

// Register the card
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'stib-wait-times-card',
  name: 'STIB Wait Times Card',
  description: 'Display STIB/MIVB wait times sorted by arrival time',
  preview: false,
  documentationURL: 'https://github.com/your-repo/stib-wait-times-card',
});

console.info(
  '%c STIB-WAIT-TIMES-CARD %c Version 1.0.0 ',
  'color: white; background: #0066cc; font-weight: bold;',
  'color: white; background: #cc0000; font-weight: bold;'
);