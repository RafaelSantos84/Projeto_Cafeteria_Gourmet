from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50))  # Ex: 'admin' ou 'user'

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id
    
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(250))

    def __repr__(self):
        return f"Product('{self.name}', '{self.price}')"

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='orders')
    products = db.relationship('OrderProduct', backref='order')
    status = db.Column(db.String(20), default='pedido realizado')


    @property
    def total_price(self):
        return sum(item.product.price * item.quantity for item in self.products)

class OrderProduct(db.Model):
    __tablename__ = 'order_product'

    id = db.Column(db.Integer, primary_key=True)  # Certifique-se de que este atributo existe
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, nullable=False)

    product = db.relationship('Product', backref='order_products')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html', pagina='index')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/products', methods=['GET', 'POST'])
@login_required
def products():
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        description = request.form['description']
        new_product = Product(name=name, price=price, description=description)
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('products'))

    products = Product.query.all()
    return render_template('products.html', products=products)

@app.route('/order', methods=['POST'])
@login_required
def order():
    product_ids = request.form.getlist('product_ids')  # Recebe os IDs dos produtos selecionados
    quantities = request.form.getlist('quantities')  # Recebe as quantidades correspondentes
    order = Order(user_id=current_user.id, status='pedido realizado')  # Define o status aqui
    
    # Adicione o pedido à sessão antes de adicionar os produtos
    db.session.add(order)
    db.session.flush()  # Força o flush para que o order.id seja gerado

    for product_id, quantity in zip(product_ids, quantities):
        order_product = OrderProduct(order_id=order.id, product_id=product_id, quantity=int(quantity))  # Crie a instância OrderProduct
        db.session.add(order_product)  # Adicione o item do pedido à sessão
    
    db.session.commit()  # Salve tudo no banco de dados
    flash('Pedido realizado com sucesso!', 'success')
    return redirect(url_for('products'))  # Redirecione após a criação do pedido



@app.route('/update_order_status/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    if current_user.role != 'admin':  # Verifica se o usuário é admin
        return "Acesso negado", 403  # Retorna erro se não for admin

    order = Order.query.get(order_id)
    if order:
        new_status = request.form['status']  # Recebe o novo status do formulário
        order.status = new_status  # Atualiza o status
        db.session.commit()
        return redirect(url_for('admin_orders'))  # Redirecione para a página de pedidos do admin
    return "Pedido não encontrado", 404


@app.route('/admin_orders')
@login_required
def admin_orders():
    if current_user.role != 'admin':  # Verifica se o usuário é admin
        return "Acesso negado", 403  # Retorna erro se não for admin

    orders = Order.query.all()  # Obtém todos os pedidos
    return render_template('admin_orders.html', orders=orders)  # Renderiza o template com todos os pedidos


@app.route('/my_orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).all()
    
    # Calculando o total de cada pedido
    for order in orders:
        total = sum(order_product.product.price * order_product.quantity for order_product in order.products)
        order.total = total  # Armazenando o total no objeto order para uso no template
    
    return render_template('my_orders.html', orders=orders)




# Rota para editar os itens do pedido - CORRIGIR (meu pedido não tem quantidade)
@app.route('/edit_order_items/<int:order_id>', methods=['GET', 'POST'])
@login_required
def edit_order_items(order_id):
    order = Order.query.get(order_id)
    
    if order and order.user_id == current_user.id:
        if request.method == 'POST':
            # Lógica para atualizar os itens do pedido
            for item in order.products:  # Aqui ainda assume-se que 'products' é a relação correta
                quantity = request.form.get(f'quantity_{item.product_id}')  # Use product_id para a chave
                if quantity is not None:
                    item.quantity = int(quantity)
            db.session.commit()
            flash('Itens do pedido atualizados com sucesso!', 'success')
            return redirect(url_for('my_orders'))

        return render_template('edit_order_items.html', order=order)
    
    return "Pedido não encontrado ou acesso negado", 404



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:  # Verificação simplificada
            login_user(user)
            return redirect(url_for('products'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Criar o banco de dados
    app.run(debug=True)