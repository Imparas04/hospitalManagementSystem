// Central API Service Layer (Flask REST API Ready)
const API_BASE_URL = 'http://127.0.0.1:5000/api';
const USE_MOCK = true; // Set to false when connecting to Python Flask backend

const ApiService = {
  // GET Requests (Read data)
  async get(endpoint) {
    if (USE_MOCK) {
      const db = Store.getData();
      if (endpoint === '/kpis') return { success: true, data: db.kpis };
      if (endpoint === '/patients') return { success: true, data: db.patients };
      if (endpoint === '/emergency') return { success: true, data: db.emergency };
      if (endpoint === '/beds') return { success: true, data: db.beds };
      return { success: false, message: 'Endpoint not found' };
    }

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`);
      return await response.json();
    } catch (error) {
      console.error('API GET Error:', error);
      return { success: false, message: error.message };
    }
  },

  // POST Requests (Add new data)
  async post(endpoint, payload) {
    if (USE_MOCK) {
      const db = Store.getData();
      if (endpoint === '/patients') {
        const newPatient = {
          id: `P-${Math.floor(1000 + Math.random() * 9000)}`,
          date: new Date().toISOString().split('T')[0],
          status: 'Waiting',
          ...payload
        };
        db.patients.unshift(newPatient);
        db.kpis.totalPatients += 1;
        Store.saveData(db);
        return { success: true, data: newPatient };
      }
      return { success: false, message: 'Endpoint not found' };
    }

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      return await response.json();
    } catch (error) {
      console.error('API POST Error:', error);
      return { success: false, message: error.message };
    }
  }
};