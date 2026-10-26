/* config.js — the only place you need to edit if the backend runs somewhere else.

   Default: Flask backend on this computer, port 5000.
   To use another address WITHOUT editing this file, run once in the browser console:
       localStorage.setItem('hospital_api_url', 'https://your-server.example.com/api')
*/
window.HOSPITAL_CONFIG = {
  apiUrl: localStorage.getItem('hospital_api_url') || 'http://127.0.0.1:5000/api',
};
