const dotenv = require('dotenv');

module.exports = async ({ resolveVariable }) => {
    const stage = await resolveVariable('opt:stage');
    const file = `${stage}.env`;
    console.log(`resolving configurations from ${file}`);
    const env = dotenv.config({ path: file }).parsed;
    return Object.assign({}, env);
};
