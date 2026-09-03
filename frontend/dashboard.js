/**
 * EnergyIQ Dashboard — JavaScript Controller
 * Fetches data from Flask APIs, renders Chart.js charts, handles predictions.
 */

// ── Chart.js Global Config ──────────────────────────────────────
Chart.defaults.color = '#8b8fa3';
Chart.defaults.borderColor = 'rgba(99, 102, 241, 0.08)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;

const CHART_COLORS = {
    indigo:  { bg: 'rgba(99, 102, 241, 0.15)',  border: '#6366f1' },
    violet:  { bg: 'rgba(139, 92, 246, 0.15)',   border: '#8b5cf6' },
    emerald: { bg: 'rgba(16, 185, 129, 0.15)',   border: '#10b981' },
    amber:   { bg: 'rgba(245, 158, 11, 0.15)',   border: '#f59e0b' },
    red:     { bg: 'rgba(239, 68, 68, 0.15)',     border: '#ef4444' },
    cyan:    { bg: 'rgba(6, 182, 212, 0.15)',     border: '#06b6d4' },
    pink:    { bg: 'rgba(236, 72, 153, 0.15)',    border: '#ec4899' },
};

const ROOM_COLORS = ['#6366f1', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444'];
const DEVICE_COLORS = ['#06b6d4', '#ec4899', '#f59e0b', '#8b5cf6'];

// ── Chart instances ─────────────────────────────────────────────
let charts = {};

// ── API Helpers ─────────────────────────────────────────────────
async function fetchJSON(url, options = {}) {
    try {
        const resp = await fetch(url, options);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error(`API Error (${url}):`, err);
        return null;
    }
}

// ── Number Formatting ───────────────────────────────────────────
function fmt(num, decimals = 1) {
    if (num == null || isNaN(num)) return '--';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return Number(num).toFixed(decimals);
}

// ── Load Summary Data ───────────────────────────────────────────
async function loadSummary() {
    const data = await fetchJSON('/api/analytics');
    if (!data || !data.summary) return;

    const s = data.summary;
    document.getElementById('totalEnergy').textContent = fmt(s.total_kwh, 0);
    document.getElementById('totalCost').textContent = '₹' + fmt(s.total_cost_inr, 0);
    document.getElementById('avgPower').textContent = fmt(s.avg_power, 0);
    document.getElementById('peakPower').textContent = fmt(s.peak_power, 0);
    document.getElementById('totalRooms').textContent = s.rooms || '--';
    document.getElementById('totalReadings').textContent = fmt(s.total_readings, 0);
    document.getElementById('livePower').textContent = fmt(s.avg_power, 0) + ' W';

    return data;
}

// ── Create / Update Charts ──────────────────────────────────────

function createGradient(ctx, color1, color2) {
    const gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, color1);
    gradient.addColorStop(1, color2);
    return gradient;
}

function renderDailyChart(data) {
    const ctx = document.getElementById('dailyChart').getContext('2d');
    if (charts.daily) charts.daily.destroy();

    const labels = data.map(d => d.date);
    const values = data.map(d => d.total_kwh);

    const gradient = createGradient(ctx, 'rgba(99, 102, 241, 0.25)', 'rgba(99, 102, 241, 0.01)');

    charts.daily = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Daily kWh',
                data: values,
                borderColor: CHART_COLORS.indigo.border,
                backgroundColor: gradient,
                fill: true,
                tension: 0.4,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 5,
                pointHoverBackgroundColor: '#6366f1',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(17, 17, 28, 0.95)',
                    borderColor: 'rgba(99, 102, 241, 0.3)',
                    borderWidth: 1,
                    padding: 12,
                    titleFont: { weight: '600' },
                    callbacks: {
                        label: ctx => `${ctx.parsed.y.toFixed(1)} kWh`
                    }
                }
            },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 10, maxRotation: 0 },
                    grid: { display: false }
                },
                y: {
                    ticks: { callback: v => v + ' kWh' },
                    grid: { color: 'rgba(99, 102, 241, 0.06)' }
                }
            }
        }
    });
}

function renderRoomChart(data) {
    const ctx = document.getElementById('roomChart').getContext('2d');
    if (charts.room) charts.room.destroy();

    charts.room = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.map(d => d.room),
            datasets: [{
                data: data.map(d => d.total_kwh),
                backgroundColor: ROOM_COLORS.map(c => c + '30'),
                borderColor: ROOM_COLORS,
                borderWidth: 2,
                hoverOffset: 8,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '62%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { padding: 14, font: { size: 11 } }
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 17, 28, 0.95)',
                    borderColor: 'rgba(99, 102, 241, 0.3)',
                    borderWidth: 1,
                    callbacks: {
                        label: ctx => ` ${ctx.label}: ${ctx.parsed.toFixed(1)} kWh`
                    }
                }
            }
        }
    });
}

function renderDeviceChart(data) {
    const ctx = document.getElementById('deviceChart').getContext('2d');
    if (charts.device) charts.device.destroy();

    charts.device = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.device),
            datasets: [{
                label: 'Total kWh',
                data: data.map(d => d.total_kwh),
                backgroundColor: DEVICE_COLORS.map(c => c + '40'),
                borderColor: DEVICE_COLORS,
                borderWidth: 2,
                borderRadius: 8,
                borderSkipped: false,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(17, 17, 28, 0.95)',
                    borderColor: 'rgba(99, 102, 241, 0.3)',
                    borderWidth: 1,
                }
            },
            scales: {
                x: { grid: { color: 'rgba(99, 102, 241, 0.06)' } },
                y: { grid: { display: false } }
            }
        }
    });
}

function renderHourlyChart(data) {
    const ctx = document.getElementById('hourlyChart').getContext('2d');
    if (charts.hourly) charts.hourly.destroy();

    const labels = data.map(d => d.hour + ':00');
    const values = data.map(d => d.avg_power);

    const gradient = createGradient(ctx, 'rgba(139, 92, 246, 0.3)', 'rgba(6, 182, 212, 0.05)');

    charts.hourly = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Avg Power (W)',
                data: values,
                backgroundColor: ctx => {
                    const idx = ctx.dataIndex;
                    // Highlight peak hours
                    if (values[idx] === Math.max(...values)) return 'rgba(239, 68, 68, 0.5)';
                    if (idx >= 12 && idx <= 16) return 'rgba(245, 158, 11, 0.35)';
                    return 'rgba(99, 102, 241, 0.25)';
                },
                borderColor: ctx => {
                    const idx = ctx.dataIndex;
                    if (values[idx] === Math.max(...values)) return '#ef4444';
                    if (idx >= 12 && idx <= 16) return '#f59e0b';
                    return '#6366f1';
                },
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(17, 17, 28, 0.95)',
                    callbacks: {
                        label: ctx => `${ctx.parsed.y.toFixed(0)} W avg`
                    }
                }
            },
            scales: {
                x: {
                    ticks: { maxRotation: 0, font: { size: 10 } },
                    grid: { display: false }
                },
                y: {
                    ticks: { callback: v => v + 'W' },
                    grid: { color: 'rgba(99, 102, 241, 0.06)' }
                }
            }
        }
    });
}

function renderMonthlyChart(data) {
    const ctx = document.getElementById('monthlyChart').getContext('2d');
    if (charts.monthly) charts.monthly.destroy();

    const gradient = createGradient(ctx, 'rgba(16, 185, 129, 0.3)', 'rgba(16, 185, 129, 0.02)');

    charts.monthly = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.year_month),
            datasets: [{
                label: 'Monthly kWh',
                data: data.map(d => d.total_kwh),
                backgroundColor: gradient,
                borderColor: '#10b981',
                borderWidth: 2,
                borderRadius: 8,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(17, 17, 28, 0.95)',
                    callbacks: {
                        label: ctx => `${ctx.parsed.y.toFixed(0)} kWh | ₹${(ctx.parsed.y * 6.5).toFixed(0)}`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    ticks: { callback: v => fmt(v, 0) + ' kWh' },
                    grid: { color: 'rgba(99, 102, 241, 0.06)' }
                }
            }
        }
    });
}

// ── Model Performance ───────────────────────────────────────────
async function loadModelInfo() {
    const data = await fetchJSON('/api/model-info');
    if (!data || !data.metrics) return;

    const metrics = data.metrics;
    const bestName = metrics.best_model || 'Unknown';
    const best = metrics[bestName] || {};

    document.getElementById('modelBadge').textContent = bestName;
    document.getElementById('metricR2').textContent = best.r2 != null ? best.r2.toFixed(4) : '--';
    document.getElementById('metricMAE').textContent = best.mae != null ? best.mae.toFixed(4) : '--';
    document.getElementById('metricRMSE').textContent = best.rmse != null ? best.rmse.toFixed(4) : '--';

    // Scatter plot: actual vs predicted
    if (data.training_results && data.training_results.length > 0) {
        renderScatterChart(data.training_results);
    }

    // Feature importances
    if (best.feature_importances) {
        renderFeatureChart(best.feature_importances);
    }
}

function renderScatterChart(results) {
    const ctx = document.getElementById('scatterChart').getContext('2d');
    if (charts.scatter) charts.scatter.destroy();

    const points = results.map(r => ({ x: r.actual, y: r.predicted }));
    const maxVal = Math.max(
        ...results.map(r => Math.max(r.actual, r.predicted))
    );

    charts.scatter = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'Predictions',
                    data: points,
                    backgroundColor: 'rgba(99, 102, 241, 0.35)',
                    borderColor: '#6366f1',
                    borderWidth: 1,
                    pointRadius: 2.5,
                    pointHoverRadius: 5,
                },
                {
                    label: 'Perfect Fit',
                    data: [{ x: 0, y: 0 }, { x: maxVal, y: maxVal }],
                    type: 'line',
                    borderColor: 'rgba(16, 185, 129, 0.5)',
                    borderDash: [6, 4],
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: false,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { padding: 12, font: { size: 11 } }
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 17, 28, 0.95)',
                    callbacks: {
                        label: ctx => `Actual: ${ctx.parsed.x.toFixed(3)} | Predicted: ${ctx.parsed.y.toFixed(3)}`
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Actual (kWh)', color: '#8b8fa3' },
                    grid: { color: 'rgba(99, 102, 241, 0.06)' }
                },
                y: {
                    title: { display: true, text: 'Predicted (kWh)', color: '#8b8fa3' },
                    grid: { color: 'rgba(99, 102, 241, 0.06)' }
                }
            }
        }
    });
}

function renderFeatureChart(importances) {
    const ctx = document.getElementById('featureChart').getContext('2d');
    if (charts.feature) charts.feature.destroy();

    // Sort by importance descending
    const sorted = Object.entries(importances)
        .sort((a, b) => b[1] - a[1]);

    const featureLabels = {
        'usage_rate': 'Device Runtime',
        'device_enc': 'Device Type',
        'room_enc': 'Room',
        'avg_temperature': 'Temperature',
        'avg_humidity': 'Humidity',
        'month': 'Month',
        'day_of_week': 'Day of Week',
        'is_weekend': 'Weekend',
    };

    charts.feature = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(([k]) => featureLabels[k] || k),
            datasets: [{
                label: 'Importance',
                data: sorted.map(([, v]) => v),
                backgroundColor: sorted.map((_, i) => {
                    const colors = Object.values(CHART_COLORS);
                    return colors[i % colors.length].bg;
                }),
                borderColor: sorted.map((_, i) => {
                    const colors = Object.values(CHART_COLORS);
                    return colors[i % colors.length].border;
                }),
                borderWidth: 2,
                borderRadius: 6,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(17, 17, 28, 0.95)',
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    grid: { color: 'rgba(99, 102, 241, 0.06)' },
                    ticks: { callback: v => (v * 100).toFixed(0) + '%' }
                }
            }
        }
    });
}

// ── Alerts & Tips ───────────────────────────────────────────────
async function loadAlerts() {
    const data = await fetchJSON('/api/alerts');
    if (!data) return;

    const alertsEl = document.getElementById('alertsList');
    const tipsEl = document.getElementById('tipsList');

    // Alerts
    if (data.alerts && data.alerts.length > 0) {
        alertsEl.innerHTML = data.alerts.map(a => `
            <div class="alert-item ${a.level}">
                <div class="alert-message">${a.message}</div>
                <div class="alert-suggestion">${a.suggestion}</div>
            </div>
        `).join('');
    } else {
        alertsEl.innerHTML = `
            <div class="alert-item info">
                <div class="alert-message">✅ All systems normal</div>
                <div class="alert-suggestion">No unusual power spikes detected.</div>
            </div>`;
    }

    // Tips
    if (data.tips && data.tips.length > 0) {
        tipsEl.innerHTML = data.tips.map(t => `
            <div class="tip-item">
                <span class="tip-icon">${t.icon}</span>
                <div class="tip-content">
                    <div class="tip-text">${t.tip}</div>
                    <div class="tip-saving">${t.potential_saving}</div>
                </div>
            </div>
        `).join('');
    }
}

// ── Prediction Form ─────────────────────────────────────────────
function setupPredictionForm() {
    const form = document.getElementById('predictForm');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const payload = {
            room: document.getElementById('predRoom').value,
            device: document.getElementById('predDevice').value,
            hour: parseInt(document.getElementById('predHour').value),
            month: parseInt(document.getElementById('predMonth').value),
            temperature: parseFloat(document.getElementById('predTemp').value),
            humidity: parseFloat(document.getElementById('predHumidity').value),
            day_of_week: 2,
            is_weekend: 0,
            usage_rate: 0.5,
        };

        const btn = document.getElementById('predictBtn');
        btn.textContent = 'Predicting...';
        btn.disabled = true;

        const data = await fetchJSON('/api/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        btn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            Predict Consumption`;
        btn.disabled = false;

        if (data && !data.error) {
            document.getElementById('predKwh').textContent = data.predicted_daily_kwh.toFixed(2) + ' kWh';
            document.getElementById('predCost').textContent = '₹' + data.estimated_daily_cost_inr.toFixed(2);
            document.getElementById('predictionResult').classList.remove('hidden');
        } else {
            alert('Prediction failed: ' + (data?.error || 'Unknown error'));
        }
    });
}

// ── Initialize ──────────────────────────────────────────────────
async function init() {
    console.log('🚀 EnergyIQ Dashboard loading...');

    // Load all data
    const analytics = await loadSummary();

    if (analytics) {
        if (analytics.daily?.length)          renderDailyChart(analytics.daily);
        if (analytics.room_totals?.length)    renderRoomChart(analytics.room_totals);
        if (analytics.device_totals?.length)  renderDeviceChart(analytics.device_totals);
        if (analytics.hourly_profile?.length) renderHourlyChart(analytics.hourly_profile);
        if (analytics.monthly?.length)        renderMonthlyChart(analytics.monthly);
    }

    await loadModelInfo();
    await loadAlerts();
    setupPredictionForm();

    console.log('✅ Dashboard ready');
}

// Start
document.addEventListener('DOMContentLoaded', init);
