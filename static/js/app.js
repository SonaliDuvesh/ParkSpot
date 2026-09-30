

document.addEventListener('DOMContentLoaded', function () {
  
  // Auto-vanish flash alerts after 2 seconds
  const flashAlerts = document.querySelectorAll('.page-body .alert, .alert-dismissible');
  flashAlerts.forEach(function (alertEl) {
    setTimeout(function () {
      if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alertEl);
        if (bsAlert) {
          bsAlert.close();
          return;
        }
      }
      alertEl.classList.remove('show');
      setTimeout(function () {
        if (alertEl && alertEl.parentNode) alertEl.parentNode.removeChild(alertEl);
      }, 300);
    }, 2000);
  });

  function updateLiveClock() {
    const clockEl = document.getElementById('liveClock');
    if (!clockEl) return;
    const now = new Date();
    const options = { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' };
    clockEl.textContent = now.toLocaleDateString('en-US', options);
  }
  updateLiveClock();
  setInterval(updateLiveClock, 30000);

  
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('appSidebar');
  const sidebarBackdrop = document.getElementById('sidebarBackdrop');

  function toggleMobileSidebar() {
    if (sidebar) sidebar.classList.toggle('show');
    if (sidebarBackdrop) sidebarBackdrop.classList.toggle('show');
  }

  if (sidebarToggle) sidebarToggle.addEventListener('click', toggleMobileSidebar);
  if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', toggleMobileSidebar);

  
  const slotFilterButtons = document.querySelectorAll('.slot-filter-btn');
  const slotCards = document.querySelectorAll('.slot-card');

  slotFilterButtons.forEach(button => {
    button.addEventListener('click', function () {
      slotFilterButtons.forEach(btn => btn.classList.remove('active', 'btn-primary'));
      slotFilterButtons.forEach(btn => btn.classList.add('btn-outline-secondary'));
      
      this.classList.remove('btn-outline-secondary');
      this.classList.add('active', 'btn-primary');

      const filter = this.getAttribute('data-filter');
      slotCards.forEach(card => {
        if (filter === 'all' || card.classList.contains('status-' + filter)) {
          card.style.display = 'block';
        } else {
          card.style.display = 'none';
        }
      });
    });
  });

  
  const vehicleTypeCards = document.querySelectorAll('.selectable-card[data-type]');
  const vehicleTypeInput = document.getElementById('vehicleTypeInput');
  const checkinSlotCards = document.querySelectorAll('.slot-select-card');
  const selectedSpotIdInput = document.getElementById('selectedSpotIdInput');
  const summarySlotEl = document.getElementById('summarySlot');
  const vehicleNoInput = document.getElementById('vehicleNoInput');

  
  const tariffsMatrix = window.PARKSPOT_TARIFFS || {
    'Car': { hourly_rate: 50.0, daily_rate: 350.0, custom_rate: 1500.0 },
    'Bike': { hourly_rate: 20.0, daily_rate: 150.0, custom_rate: 600.0 },
    'Motorcycle': { hourly_rate: 20.0, daily_rate: 150.0, custom_rate: 600.0 },
    'Scooter': { hourly_rate: 20.0, daily_rate: 150.0, custom_rate: 600.0 },
    'SUV': { hourly_rate: 70.0, daily_rate: 500.0, custom_rate: 2000.0 },
    'EV': { hourly_rate: 80.0, daily_rate: 600.0, custom_rate: 2500.0 },
    'Truck': { hourly_rate: 100.0, daily_rate: 800.0, custom_rate: 3000.0 }
  };

  function getTariffForVehicle(vType) {
    if (tariffsMatrix[vType]) return tariffsMatrix[vType];
    if (vType === 'Motorcycle' || vType === 'Scooter') return tariffsMatrix['Bike'] || { hourly_rate: 20.0, daily_rate: 150.0, custom_rate: 600.0 };
    return tariffsMatrix['Car'] || { hourly_rate: 50.0, daily_rate: 350.0, custom_rate: 1500.0 };
  }

  function filterSlotsByVehicleCompatibility() {
    const selectedType = vehicleTypeInput ? vehicleTypeInput.value : 'Car';
    const isBikeType = selectedType === 'Bike' || selectedType === 'Motorcycle' || selectedType === 'Scooter';

    const compNotice = document.getElementById('compatibilityNotice');
    if (compNotice) {
      if (isBikeType) {
        compNotice.className = 'badge bg-success-subtle text-success font-semibold';
        compNotice.innerHTML = '<i class="fas fa-motorcycle me-1"></i> Highlighted Bike/Two-Wheeler Bays';
      } else {
        compNotice.className = 'badge bg-primary-subtle text-primary font-semibold';
        compNotice.innerHTML = '<i class="fas fa-car me-1"></i> Highlighted Four-Wheeler Bays';
      }
    }

    checkinSlotCards.forEach(card => {
      const spotType = card.getAttribute('data-spot-type') || 'Car';
      const isSpotBike = spotType === 'Bike' || spotType === 'Motorcycle' || spotType === 'Scooter';

      if ((isBikeType && isSpotBike) || (!isBikeType && !isSpotBike)) {
        card.classList.remove('incompatible-slot');
        card.style.opacity = '1';
        card.style.cursor = 'pointer';
      } else {
        card.classList.add('incompatible-slot');
        card.style.opacity = '0.4';
        card.style.cursor = 'not-allowed';
      }
    });
  }

  vehicleTypeCards.forEach(card => {
    card.addEventListener('click', function () {
      vehicleTypeCards.forEach(c => c.classList.remove('active'));
      this.classList.add('active');
      const selectedType = this.getAttribute('data-type');
      if (vehicleTypeInput) vehicleTypeInput.value = selectedType;
      
      
      if (selectedSpotIdInput) selectedSpotIdInput.value = '';
      if (summarySlotEl) summarySlotEl.textContent = 'Select Slot';
      checkinSlotCards.forEach(c => c.classList.remove('selected'));

      updateCheckinSummary();
      filterSlotsByVehicleCompatibility();
    });
  });

  if (vehicleNoInput) {
    vehicleNoInput.addEventListener('input', function () {
      this.value = this.value.toUpperCase();
      updateCheckinSummary();
    });
  }

  checkinSlotCards.forEach(card => {
    card.addEventListener('click', function () {
      if (this.classList.contains('status-O') || this.classList.contains('status-M')) return;

      const spotId = this.getAttribute('data-spot-id');
      const spotNum = this.getAttribute('data-spot-num');
      const spotType = this.getAttribute('data-spot-type') || 'Car';
      const selectedVehicleType = vehicleTypeInput ? vehicleTypeInput.value : 'Car';

      const isBikeType = selectedVehicleType === 'Motorcycle' || selectedVehicleType === 'Scooter' || selectedVehicleType === 'Bike';
      const isSpotBike = spotType === 'Bike' || spotType === 'Motorcycle' || spotType === 'Scooter';

      if (isBikeType && !isSpotBike) {
        alert(`Slot ${spotNum} is designated for ${spotType}s. Please select a Bike/Two-Wheeler designated slot!`);
        return;
      }
      if (!isBikeType && isSpotBike) {
        alert(`Slot ${spotNum} is strictly reserved for Bikes/Motorcycles only. ${selectedVehicleType}s cannot park here!`);
        return;
      }

      checkinSlotCards.forEach(c => c.classList.remove('selected'));
      this.classList.add('selected');

      if (selectedSpotIdInput) selectedSpotIdInput.value = spotId;
      if (summarySlotEl) summarySlotEl.textContent = spotNum;
    });
  });

  const durationInputs = document.querySelectorAll('input[name="parking_duration"]');
  durationInputs.forEach(input => {
    input.addEventListener('change', updateCheckinSummary);
  });

  function updateCheckinSummary() {
    const vNo = vehicleNoInput ? (vehicleNoInput.value || 'RJ14 AB 1234') : 'RJ14 AB 1234';
    const vType = vehicleTypeInput ? (vehicleTypeInput.value || 'Car') : 'Car';
    
    const summaryNo = document.getElementById('summaryVehicleNo');
    const summaryType = document.getElementById('summaryVehicleType');
    const summaryPassType = document.getElementById('summaryPassType');
    const summaryRate = document.getElementById('summaryRate');

    const tariff = getTariffForVehicle(vType);

    
    const labelHourly = document.getElementById('rateLabelHourly');
    const labelDaily = document.getElementById('rateLabelDaily');
    const labelCustom = document.getElementById('rateLabelCustom');

    if (labelHourly) labelHourly.textContent = `₹${tariff.hourly_rate} / hr`;
    if (labelDaily) labelDaily.textContent = `₹${tariff.daily_rate} / day`;
    if (labelCustom) labelCustom.textContent = `₹${tariff.custom_rate} / pass`;

    if (summaryNo) summaryNo.textContent = vNo;
    if (summaryType) summaryType.textContent = vType;

    const selectedDurationEl = document.querySelector('input[name="parking_duration"]:checked');
    const durationType = selectedDurationEl ? selectedDurationEl.value : 'Hourly';

    if (summaryPassType) {
      if (durationType === 'Daily') summaryPassType.textContent = 'Daily Pass';
      else if (durationType === 'Custom') summaryPassType.textContent = 'Custom Pass';
      else summaryPassType.textContent = 'Hourly Rate';
    }

    if (summaryRate) {
      if (durationType === 'Daily') summaryRate.textContent = `₹${tariff.daily_rate} / day`;
      else if (durationType === 'Custom') summaryRate.textContent = `₹${tariff.custom_rate} / pass`;
      else summaryRate.textContent = `₹${tariff.hourly_rate} / hr`;
    }
  }

  
  if (vehicleTypeInput) {
    updateCheckinSummary();
    filterSlotsByVehicleCompatibility();
  }

  
  // Global Live Search functionality
  const headerSearch = document.getElementById('headerSearch');
  const tableSearchInput = document.getElementById('tableSearchInput');
  const searchInputs = [headerSearch, tableSearchInput].filter(Boolean);

  searchInputs.forEach(searchInput => {
    searchInput.addEventListener('input', function () {
      const query = this.value.trim().toLowerCase();

      // Synchronize other search input if present
      searchInputs.forEach(input => {
        if (input !== searchInput && input.value !== searchInput.value) {
          input.value = searchInput.value;
        }
      });

      // 1. Filter all tables on the page
      const tables = document.querySelectorAll('table');
      tables.forEach(table => {
        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const rows = tbody.querySelectorAll('tr');
        let visibleCount = 0;
        let originalRowsCount = 0;

        rows.forEach(row => {
          if (row.classList.contains('no-search-results-row')) return;
          originalRowsCount++;

          const text = row.textContent.toLowerCase();
          if (query === '' || text.includes(query)) {
            row.style.display = '';
            visibleCount++;
          } else {
            row.style.display = 'none';
          }
        });

        // Show/hide empty state placeholder row
        const existingNoResults = tbody.querySelector('.no-search-results-row');
        if (query !== '' && visibleCount === 0 && originalRowsCount > 0) {
          if (!existingNoResults) {
            const colCount = table.querySelectorAll('thead th').length || 6;
            const noResultsRow = document.createElement('tr');
            noResultsRow.className = 'no-search-results-row';
            noResultsRow.innerHTML = `<td colspan="${colCount}" class="text-center py-4 text-muted"><i class="fas fa-search me-2"></i>No matching records found for "<strong>${searchInput.value}</strong>"</td>`;
            tbody.appendChild(noResultsRow);
          }
        } else if (existingNoResults) {
          existingNoResults.remove();
        }
      });

      // 2. Filter slot cards if on a parking slot page
      const slotCards = document.querySelectorAll('.slot-card');
      slotCards.forEach(card => {
        const text = card.textContent.toLowerCase();
        if (query === '' || text.includes(query)) {
          card.style.display = '';
        } else {
          card.style.display = 'none';
        }
      });

      // 3. Filter parking lot facility cards
      const facilityCards = document.querySelectorAll('.col-12.col-xl-6:has(.card-custom), .col-md-6.col-lg-4:has(.parking-lot-card)');
      facilityCards.forEach(card => {
        const text = card.textContent.toLowerCase();
        if (query === '' || text.includes(query)) {
          card.style.display = '';
        } else {
          card.style.display = 'none';
        }
      });
    });

    // Clear search on Escape key
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        this.value = '';
        this.dispatchEvent(new Event('input'));
      }
    });
  });
});

function openSlotDetailModal(spotId, spotNumber, zone, spotType, status, vehicleNo, ownerName, phone, entryTime, duration) {
  document.getElementById('modalSpotNumber').textContent = spotNumber;
  document.getElementById('modalSpotZone').textContent = zone;
  document.getElementById('modalSpotType').textContent = spotType;
  
  const statusBadge = document.getElementById('modalSpotStatus');
  let statusText = 'Available';
  let badgeClass = 'badge-available';

  if (status === 'O') { statusText = 'Occupied'; badgeClass = 'badge-occupied'; }
  else if (status === 'R') { statusText = 'Reserved'; badgeClass = 'badge-reserved'; }
  else if (status === 'M') { statusText = 'Maintenance'; badgeClass = 'badge-maintenance'; }

  statusBadge.className = 'badge-status ' + badgeClass;
  statusBadge.textContent = statusText;

  const vehicleDetailsSec = document.getElementById('modalVehicleDetailsSection');
  if (status === 'O' || status === 'R') {
    vehicleDetailsSec.style.display = 'block';
    const heading = vehicleDetailsSec.querySelector('h6');
    if (heading) {
      heading.innerHTML = status === 'R' 
        ? '<i class="fas fa-bookmark me-2 text-warning"></i>Reserved Customer Information' 
        : '<i class="fas fa-car me-2 text-primary"></i>Currently Parked Vehicle';
    }

    document.getElementById('modalVehicleNo').textContent = vehicleNo || (status === 'R' ? 'Reserved Bay' : 'N/A');
    document.getElementById('modalOwnerName').textContent = ownerName || (status === 'R' ? 'VIP Reserved Guest' : 'N/A');
    document.getElementById('modalPhone').textContent = phone || 'N/A';
    document.getElementById('modalEntryTime').textContent = entryTime || 'Pre-booked';
    document.getElementById('modalDuration').textContent = duration || (status === 'R' ? 'Reserved Pass' : 'N/A');
  } else {
    vehicleDetailsSec.style.display = 'none';
  }

  const modalSpotIdInput = document.getElementById('modalSpotIdInput');
  if (modalSpotIdInput) modalSpotIdInput.value = spotId;

  const inputSpotNum = document.getElementById('modalInputSpotNumber');
  if (inputSpotNum) inputSpotNum.value = spotNumber;

  const inputZone = document.getElementById('modalInputZone');
  if (inputZone) inputZone.value = zone;

  const selectSpotType = document.getElementById('modalSelectSpotType');
  if (selectSpotType) selectSpotType.value = spotType;

  const selectStatus = document.getElementById('modalSelectStatus');
  if (selectStatus) selectStatus.value = status;

  const modal = new bootstrap.Modal(document.getElementById('slotDetailModal'));
  modal.show();
}

function printTicket() {
  window.print();
}
