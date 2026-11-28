import http from 'k6/http';
import { check, sleep } from 'k6';
import encoding from 'k6/encoding';

const BASE_URL = 'http://gateway:3000';

export const options = {
    stages: [
        { duration: '30s', target: 20 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 0 },
    ],

    summaryTrendStats: [
        'avg', 'min', 'max',
        'p(50)', 'p(95)', 'p(99)'
    ],
};

export function setup() {
    const user = {
        email: `load-${Date.now()}@example.com`,
        password: 'Lab9Load123!'
    };

    const response = http.post(
        `${BASE_URL}/auth/register`,
        JSON.stringify(user),
        {
            headers: {
                'Content-Type': 'application/json'
            }
        }
    );

    if (response.status !== 200) {
        throw new Error('Registration failed');
    }

    return user;
}

export default function (user) {
    // 1. Login
    const loginRes = http.post(
        `${BASE_URL}/auth/login`,
        JSON.stringify(user),
        {
            headers: {
                'Content-Type': 'application/json'
            }
        }
    );

    if (!check(loginRes, {
        'login success': r => r.status === 200
    })) {
        sleep(1);
        return;
    }

    const token = loginRes.json('access_token');

    const payload = JSON.parse(
        encoding.b64decode(
            token.split('.')[1], 'rawurl', 's'
        )
    );

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };

    // 2. Catalog
    const catalogRes = http.get(
        `${BASE_URL}/catalog/products`,
        { headers }
    );

    if (!check(catalogRes, {
        'catalog success': r => r.status === 200
    })) {
        sleep(1);
        return;
    }

    const products = catalogRes.json('products');

    if (!check(products, {
        'catalog is not empty': p => p.length > 0
    })) {
        sleep(1);
        return;
    }

    const product = products[0];

    // 3. Create order
    const orderRes = http.post(
        `${BASE_URL}/orders`,
        JSON.stringify({
            user_id: payload.sub,
            items: [
                {
                    product_id: product.id,
                    quantity: 1
                }
            ],
            amount: product.price
        }),
        { headers }
    );

    check(orderRes, {
        'order created': r => r.status === 201
    });

    sleep(1);
}