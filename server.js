import express from 'express';
import bodyParser from 'body-parser';
import axios from 'axios';

const app = express();
app.use(bodyParser.json());

// === CONFIGURAZIONE ===
const IG_API_KEY = 'f238c03996ba52d15d291ee0bdfff82099511429';
const IG_USERNAME = 'biagiob@icloud.com';
const IG_PASSWORD = 'P1x3y013579??';
const EXPECTED_SECRET = 'tv_ig_2025_secret!';

let CST_TOKEN = null;
let SECURITY_TOKEN = null;

// === Funzione di login automatico ===
async function loginIG() {
  try {
    const response = await axios.post(
      'https://api.ig.com/gateway/deal/session',
      {
        identifier: IG_USERNAME,
        password: IG_PASSWORD
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-IG-API-KEY': IG_API_KEY
        }
      }
    );

    CST_TOKEN = response.headers['cst'];
    SECURITY_TOKEN = response.headers['x-security-token'];

    console.log('✅ Login IG riuscito');
    console.log('CST:', CST_TOKEN);
    console.log('X-SECURITY-TOKEN:', SECURITY_TOKEN);
  } catch (error) {
    if (error.response) {
      console.error('❌ Errore login IG:', error.response.data);
    } else {
      console.error('❌ Errore login IG:', error.message);
    }
  }
}

// === Funzione per inviare ordini a IG ===
async function sendOrderToIG(order) {
  try {
    const response = await axios.post(
      'https://api.ig.com/gateway/deal/positions/otc',
      order,
      {
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-IG-API-KEY': IG_API_KEY,
          'CST': CST_TOKEN,
          'X-SECURITY-TOKEN': SECURITY_TOKEN
        }
      }
    );

    console.log('✅ Ordine IG eseguito:', response.data);
    return response.data;
  } catch (error) {
    if (error.response) {
      console.error('❌ Errore IG:', error.response.data);

      // Se i token sono invalidi, rifaccio login e riprovo
      if (error.response.data.errorCode === 'error.security.client-token-invalid') {
        console.log('🔄 Token scaduti, rifaccio login...');
        await loginIG();
        return await sendOrderToIG(order);
      }

      return error.response.data; // restituisce l’errore completo
    } else {
      console.error('❌ Errore IG:', error.message);
      return { error: error.message };
    }
  }
}

// === ENDPOINT WEBHOOK ===
app.post('/webhook', async (req, res) => {
  const payload = req.body;

  if (payload.secret !== EXPECTED_SECRET) {
    console.log('❌ Secret non valido:', payload.secret);
    return res.status(403).send('Forbidden');
  }

  console.log('✅ Webhook ricevuto:', JSON.stringify(payload));

  let igOrder = {
    epic: payload.epic,
    expiry: '-',
    direction: payload.direction,
    size: payload.size,
    orderType: payload.orderType,
    guaranteedStop: false,
    currencyCode: payload.currencyCode,
    forceOpen: true
  };

  const result = await sendOrderToIG(igOrder);
  res.json(result); // restituisce SEMPRE la risposta completa di IG
});

// === AVVIO SERVER ===
const PORT = process.env.PORT || 3000;
app.listen(PORT, async () => {
  console.log(`🚀 Server attivo su porta ${PORT}`);
  await loginIG(); // login automatico all'avvio
});