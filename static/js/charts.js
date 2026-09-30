

document.addEventListener('DOMContentLoaded', function () {
  
  const entriesCtx = document.getElementById('entriesChart');
  if (entriesCtx) {
    new Chart(entriesCtx, {
      type: 'line',
      data: {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        datasets: [{
          label: 'Vehicle Check-Ins',
          data: [65, 78, 90, 81, 105, 120, 95],
          borderColor: '#4f46e5',
          backgroundColor: 'rgba(79, 70, 229, 0.1)',
          tension: 0.35,
          fill: true,
          pointBackgroundColor: '#4f46e5',
          pointRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
          x: { grid: { display: false } }
        }
      }
    });
  }

  
  const occupancyCtx = document.getElementById('occupancyChart');
  if (occupancyCtx) {
    new Chart(occupancyCtx, {
      type: 'doughnut',
      data: {
        labels: ['Available', 'Occupied', 'Reserved', 'Maintenance'],
        datasets: [{
          data: [42, 68, 10, 5],
          backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'],
          borderWidth: 2,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, padding: 15 } }
        }
      }
    });
  }

  
  const revenueCtx = document.getElementById('revenueChart');
  if (revenueCtx) {
    new Chart(revenueCtx, {
      type: 'bar',
      data: {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        datasets: [{
          label: 'Revenue (₹)',
          data: [4200, 5600, 6100, 5800, 7900, 9400, 8200],
          backgroundColor: '#6366f1',
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
          x: { grid: { display: false } }
        }
      }
    });
  }

  
  const typeCtx = document.getElementById('vehicleTypeChart');
  if (typeCtx) {
    new Chart(typeCtx, {
      type: 'pie',
      data: {
        labels: ['Cars', 'Motorcycles', 'SUVs', 'Scooters', 'EVs', 'Trucks'],
        datasets: [{
          data: [45, 25, 15, 8, 5, 2],
          backgroundColor: ['#4f46e5', '#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, padding: 15 } }
        }
      }
    });
  }
});